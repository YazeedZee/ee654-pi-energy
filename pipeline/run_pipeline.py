#!/usr/bin/env python3
"""Pipeline v1: decode -> to_bgr -> detect (every N frames) -> overlay -> to_yuv -> encode.

One process, stages run in sequence per frame. Frames are released at a fixed rate
(--fps, default 30) as if from a camera; each frame's deadline is one period after
its release. A late frame does not cause drops: the next frame starts immediately,
so lateness accumulates and shows up as deadline misses.

The run stops after --duration seconds of wall-clock time, however many frames that is.
Per-frame service time (sum of all stages, excluding waiting) is logged separately from
latency: when the pipeline is overloaded (utilization = mean service / period > 1),
latency grows without bound and only service time and throughput are meaningful.

Modes:
  sw  software H.264 decode (ffmpeg 'h264') and encode (libx264, veryfast, zerolatency)
  hw  hardware codec for both (h264_v4l2m2m decode and encode)
The detector (OpenCV DNN, MobileNet-SSD) runs on the CPU in both modes.

Colour conversion of decoded frames (--convert):
  copy    (default) bulk-copy the decoded planes into normal memory, then convert with OpenCV.
  direct  PyAV/swscale conversion straight from the decoder's buffer. Exp 03 showed this
          takes ~138 ms per 720p frame on hardware-decoded frames (vs ~4 ms with copy),
          because of how it reads the decoder's memory. Kept for comparison.
Both modes use the same method, so the sw/hw comparison stays fair.

Outputs in --out-dir:
  frames.csv    one row per frame: stage times, latency, deadline miss, temperature
  summary.json  configuration, versions and summary statistics (warm-up excluded)
Input packets are loaded into RAM before the run, so storage reads do not add noise.
"""
import argparse
import csv
import json
import os
import platform
import resource
import time
from fractions import Fraction
from pathlib import Path

import av
import cv2
import numpy as np

VOC_CLASSES = ["background", "aeroplane", "bicycle", "bird", "boat", "bottle", "bus", "car",
               "cat", "chair", "cow", "diningtable", "dog", "horse", "motorbike", "person",
               "pottedplant", "sheep", "sofa", "train", "tvmonitor"]
PERSON = VOC_CLASSES.index("person")
TEMP_PATH = "/sys/class/thermal/thermal_zone0/temp"
FREQ_PATH = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"
CODECS = {"sw": ("h264", "libx264"), "hw": ("h264_v4l2m2m", "h264_v4l2m2m")}


def read_int(path):
    try:
        with open(path) as f:
            return int(f.read().strip())
    except OSError:
        return -1


def read_temp():
    t = read_int(TEMP_PATH)
    return t / 1000 if t >= 0 else None


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True, help="H.264 video file (mp4)")
    p.add_argument("--mode", choices=["sw", "hw"], required=True)
    p.add_argument("--duration", type=float, default=180, help="run length in wall-clock seconds (input loops)")
    p.add_argument("--fps", type=float, default=30, help="frame release rate; deadline = 1/fps")
    p.add_argument("--detect-every", type=int, default=1, help="run the detector every N frames")
    p.add_argument("--conf", type=float, default=0.5, help="detection confidence threshold")
    p.add_argument("--bitrate", type=int, default=4_000_000)
    p.add_argument("--warmup", type=float, default=2.0, help="seconds excluded from summary stats")
    p.add_argument("--free-run", action="store_true", help="no pacing: process frames as fast as possible")
    p.add_argument("--convert", choices=["copy", "direct"], default="copy",
                   help="decoded-frame colour conversion: bulk copy then OpenCV (default) or PyAV direct")
    p.add_argument("--model-dir", default=str(Path(__file__).resolve().parent / "models"))
    p.add_argument("--out-dir", required=True)
    return p.parse_args()


def load_packets(path):
    """Demux the whole file into memory. Returns (packets, codec params)."""
    with av.open(path) as c:
        s = c.streams.video[0]
        params = {"width": s.codec_context.width, "height": s.codec_context.height,
                  "extradata": s.codec_context.extradata, "codec": s.codec_context.name}
        pkts = [bytes(p) for p in c.demux(s) if p.size > 0]
    return pkts, params


def open_decoder(name, params):
    d = av.CodecContext.create(name, "r")
    d.width, d.height = params["width"], params["height"]
    if params["extradata"]:
        d.extradata = params["extradata"]
    d.open()
    return d


def open_encoder(name, w, h, fps, bitrate):
    e = av.CodecContext.create(name, "w")
    e.width, e.height = w, h
    e.pix_fmt = "yuv420p"
    e.time_base = Fraction(1, int(round(fps)))
    e.framerate = Fraction(int(round(fps)), 1)
    e.bit_rate = bitrate
    e.gop_size = int(round(fps))
    if name == "libx264":
        e.options = {"preset": "veryfast", "tune": "zerolatency"}
    e.open()
    return e


def frame_source(decoder, packets):
    """Yield decoded frames forever, looping over the in-memory packets."""
    while True:
        for data in packets:
            for f in decoder.decode(av.Packet(data)):
                yield f


def planes_to_i420(frame):
    """Bulk-copy a yuv420p frame's planes (honouring line padding) into one contiguous I420 array."""
    w, h = frame.width, frame.height
    out = np.empty((h * 3 // 2, w), dtype=np.uint8)
    out[:h] = np.frombuffer(frame.planes[0], np.uint8).reshape(-1, frame.planes[0].line_size)[:h, :w]
    cw, ch = w // 2, h // 2
    for k, p in enumerate(frame.planes[1:3]):
        c = np.frombuffer(p, np.uint8).reshape(-1, p.line_size)[:ch, :cw]
        out[h + k * ch // 2: h + (k + 1) * ch // 2] = c.reshape(-1, w)
    return out


def to_bgr(frame, method):
    if method == "copy" and frame.format.name == "yuv420p":
        return cv2.cvtColor(planes_to_i420(frame), cv2.COLOR_YUV2BGR_I420)
    return frame.to_ndarray(format="bgr24")


def load_detector(model_dir):
    proto = Path(model_dir) / "deploy.prototxt"
    weights = Path(model_dir) / "mobilenet_iter_73000.caffemodel"
    if not proto.exists() or not weights.exists():
        raise SystemExit(f"Model files missing in {model_dir}. Run scripts/fetch_model.sh first.")
    return cv2.dnn.readNetFromCaffe(str(proto), str(weights))


def detect(net, img, conf):
    blob = cv2.dnn.blobFromImage(cv2.resize(img, (300, 300)), 0.007843, (300, 300), 127.5)
    net.setInput(blob)
    out = net.forward()[0, 0]
    h, w = img.shape[:2]
    boxes = []
    for det in out:
        if det[2] >= conf:
            x1, y1, x2, y2 = (det[3:7] * np.array([w, h, w, h])).astype(int)
            boxes.append((int(det[1]), float(det[2]), x1, y1, x2, y2))
    return boxes


def pct(a, q):
    return float(np.percentile(a, q)) if len(a) else None


def main():
    a = parse_args()
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    dec_name, enc_name = CODECS[a.mode]

    packets, params = load_packets(a.input)
    w, h = params["width"], params["height"]
    net = load_detector(a.model_dir)
    dec = open_decoder(dec_name, params)
    enc = open_encoder(enc_name, w, h, a.fps, a.bitrate)
    src = frame_source(dec, packets)

    period = 1.0 / a.fps
    boxes = []
    rows = []
    ru0 = resource.getrusage(resource.RUSAGE_SELF)
    t_start = time.perf_counter()
    wall_start = time.time()

    i = -1
    while time.perf_counter() - t_start < a.duration:
        i += 1
        release = t_start + i * period
        now = time.perf_counter()
        if not a.free_run and now < release:
            time.sleep(release - now)
        if a.free_run:
            release = time.perf_counter()

        t0 = time.perf_counter()
        frame = next(src)
        t1 = time.perf_counter()
        img = to_bgr(frame, a.convert)
        t2 = time.perf_counter()
        ran_detect = (i % a.detect_every == 0)
        if ran_detect:
            boxes = detect(net, img, a.conf)
        t3 = time.perf_counter()
        for cls, score, x1, y1, x2, y2 in boxes:
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0) if cls == PERSON else (255, 160, 0), 2)
        t4 = time.perf_counter()
        vf = av.VideoFrame.from_ndarray(img, format="bgr24").reformat(format="yuv420p")
        vf.pts = i
        t5 = time.perf_counter()
        enc_bytes = sum(p.size for p in enc.encode(vf))
        t6 = time.perf_counter()

        latency = t6 - release
        rows.append([i, round(wall_start + (release - t_start), 6), round(latency * 1e3, 3),
                     int(latency > period), round((t6 - t0) * 1e3, 3),
                     round((t1 - t0) * 1e3, 3), round((t2 - t1) * 1e3, 3), round((t3 - t2) * 1e3, 3),
                     round((t4 - t3) * 1e3, 3), round((t5 - t4) * 1e3, 3), round((t6 - t5) * 1e3, 3),
                     int(ran_detect), sum(1 for b in boxes if b[0] == PERSON), enc_bytes,
                     read_temp(), read_int(FREQ_PATH)])

    t_end = time.perf_counter()
    n_frames = len(rows)
    ru1 = resource.getrusage(resource.RUSAGE_SELF)
    for p in enc.encode(None):
        pass

    cols = ["frame", "release_wall_s", "latency_ms", "miss", "service_ms", "decode_ms", "to_bgr_ms", "detect_ms",
            "overlay_ms", "to_yuv_ms", "encode_ms", "detected", "persons", "enc_bytes",
            "temp_c", "scaling_cur_freq_khz"]
    with open(out / "frames.csv", "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(cols)
        wr.writerows(rows)

    arr = np.array([r[2:13] for r in rows], dtype=float)
    warm = int(np.searchsorted(np.array([r[1] for r in rows]) - wall_start, a.warmup))
    keep = arr[warm:] if len(arr) > warm else arr
    lat, miss, svc = keep[:, 0], keep[:, 1], keep[:, 2]
    stage_names = ["decode", "to_bgr", "detect", "overlay", "to_yuv", "encode"]
    stages = {}
    for k, name in enumerate(stage_names):
        col = keep[:, 3 + k]
        if name == "detect":
            col = col[keep[:, 9] == 1]
        stages[name] = {"mean_ms": float(col.mean()) if len(col) else None,
                        "p50_ms": pct(col, 50), "p99_ms": pct(col, 99), "max_ms": float(col.max()) if len(col) else None}
    elapsed = t_end - t_start
    cpu_s = (ru1.ru_utime - ru0.ru_utime) + (ru1.ru_stime - ru0.ru_stime)
    summary = {
        "config": {**vars(a), "decoder": dec_name, "encoder": enc_name, "width": w, "height": h,
                   "input_codec": params["codec"], "input_packets": len(packets)},
        "versions": {"python": platform.python_version(), "pyav": av.__version__, "opencv": cv2.__version__,
                     "opencv_threads": cv2.getNumThreads(), "host": platform.node(), "kernel": platform.release()},
        "frames": n_frames,
        "frames_in_stats": int(len(keep)),
        "elapsed_s": elapsed,
        "achieved_fps": n_frames / elapsed,
        "deadline_ms": period * 1e3,
        "miss_ratio": float(miss.mean()) if len(miss) else None,
        "latency_ms": {"p50": pct(lat, 50), "p99": pct(lat, 99), "max": float(lat.max()) if len(lat) else None},
        "service_ms": {"mean": float(svc.mean()) if len(svc) else None, "p50": pct(svc, 50),
                       "p99": pct(svc, 99), "max": float(svc.max()) if len(svc) else None},
        "utilization": float(svc.mean() / (period * 1e3)) if len(svc) else None,
        "overloaded": bool(len(svc) and svc.mean() > period * 1e3),
        "stages": stages,
        "cpu_s": cpu_s,
        "cpu_cores_used": cpu_s / elapsed,
        "cpu_ms_per_frame": cpu_s / n_frames * 1e3,
        "temp_c": {"start": rows[0][14], "end": rows[-1][14],
                   "max": max((r[14] for r in rows if r[14] is not None), default=None)},
    }
    with open(out / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"{a.mode}: {summary['achieved_fps']:.1f} fps, utilization {summary['utilization']:.2f}"
          f"{' (OVERLOADED)' if summary['overloaded'] else ''}, miss {100 * (summary['miss_ratio'] or 0):.1f}%, "
          f"service p50 {summary['service_ms']['p50']:.1f} / p99 {summary['service_ms']['p99']:.1f} ms, "
          f"{summary['cpu_cores_used']:.2f} cores, temp {summary['temp_c']['start']}->{summary['temp_c']['end']} C")


if __name__ == "__main__":
    main()
