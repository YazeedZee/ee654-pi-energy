#!/usr/bin/env python3
"""Pipeline v2: two periodic real-time tasks with rate-monotonic priorities.

  Frame task  (period T = 1/fps, deadline T):
      decode -> to_bgr -> [hand frame to detector every N frames] -> overlay -> to_yuv -> encode
  Detect task (period N*T, deadline N*T):
      MobileNet-SSD on the latest handed-over frame; publishes boxes the frame task draws.

Rate-monotonic (RM) order: shorter period = higher priority, so frame task > detect task.
  --sched rms  frame thread SCHED_FIFO prio 80, detect thread SCHED_FIFO prio 70
  --sched cfs  both threads normal Linux scheduling (SCHED_OTHER), for comparison
--cores restricts the whole process (and every thread it creates) to the given CPUs.
With one core, --cv-threads 1 and --codec-threads 1 the system is a uniprocessor and the
classic analysis applies: Liu & Layland bound and response-time analysis (RTA).

Execution time C of each job is measured from its thread's own CPU time
(time.thread_time), which excludes time spent preempted or waiting for the video hardware.
Response time R is wall-clock time from release to completion.
Notes for interpretation:
  * hw mode decode/encode wait for the video hardware without using the CPU: the frame
    task is partly self-suspending, so wall service time > CPU time even with no interference.
  * Python's GIL is a lock shared by both threads; time the detect thread holds it can block
    the frame thread (a possible priority-inversion source), visible as R_frame - C_frame.
  * A hand-over that finds the previous detection job not yet started overwrites it
    (counted as 'skipped' detection jobs).

Outputs in --out-dir: frames.csv, detect.csv, summary.json (with the analysis).
Requires rtprio permission for --sched rms (scripts/setup_pi.sh sets it; log in again after).
"""
import argparse
import csv
import json
import math
import os
import platform
import threading
import time
from fractions import Fraction
from pathlib import Path

import av
import cv2
import numpy as np

from run_pipeline import (CODECS, FREQ_PATH, GOV_PATH, PERSON, detect, frame_source, load_detector,
                          load_packets, pct, planes_to_i420, read_int, read_temp)

PRIO_FRAME, PRIO_DETECT = 80, 70
LL_BOUND_2 = 2 * (2 ** 0.5 - 1)          # Liu & Layland bound for 2 tasks = 0.8284


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--input", required=True)
    p.add_argument("--mode", choices=["sw", "hw"], required=True)
    p.add_argument("--sched", choices=["cfs", "rms"], required=True)
    p.add_argument("--duration", type=float, default=90, help="wall-clock seconds")
    p.add_argument("--fps", type=float, default=15)
    p.add_argument("--detect-every", type=int, default=10, help="N: detect period = N frame periods")
    p.add_argument("--cores", default="3", help="comma-separated CPU list, e.g. '3' or '0,1,2,3'")
    p.add_argument("--cv-threads", type=int, default=1)
    p.add_argument("--codec-threads", type=int, default=1)
    p.add_argument("--conf", type=float, default=0.5)
    p.add_argument("--bitrate", type=int, default=4_000_000)
    p.add_argument("--warmup", type=float, default=3.0, help="seconds excluded from statistics")
    p.add_argument("--model-dir", default=str(Path(__file__).resolve().parent / "models"))
    p.add_argument("--out-dir", required=True)
    return p.parse_args()


def set_fifo(prio):
    """Make the calling thread SCHED_FIFO at prio (Linux applies pid 0 to the calling thread)."""
    try:
        os.sched_setscheduler(0, os.SCHED_FIFO, os.sched_param(prio))
    except PermissionError:
        raise SystemExit("Cannot set SCHED_FIFO: no rtprio permission. Run scripts/setup_pi.sh, "
                         "then log out and back in (check with: ulimit -r).")


def open_decoder(name, params, threads):
    d = av.CodecContext.create(name, "r")
    d.width, d.height = params["width"], params["height"]
    if params["extradata"]:
        d.extradata = params["extradata"]
    d.thread_count = threads
    d.open()
    return d


def open_encoder(name, w, h, fps, bitrate, threads):
    e = av.CodecContext.create(name, "w")
    e.width, e.height, e.pix_fmt = w, h, "yuv420p"
    e.time_base = Fraction(1, int(round(fps)))
    e.framerate = Fraction(int(round(fps)), 1)
    e.bit_rate, e.gop_size, e.thread_count = bitrate, int(round(fps)), threads
    if name == "libx264":
        e.options = {"preset": "veryfast", "tune": "zerolatency"}
    e.open()
    return e


def to_bgr(frame):
    """Bulk-copy the decoded planes, then convert with libswscale (single thread, no OpenCV pool,
    so the frame task never queues behind detection inside OpenCV's shared thread pool)."""
    if frame.format.name == "yuv420p":
        return av.VideoFrame.from_ndarray(planes_to_i420(frame), format="yuv420p").to_ndarray(format="bgr24")
    return frame.to_ndarray(format="bgr24")


class Mailbox:
    """One-slot hand-over from the frame task to the detect task."""

    def __init__(self):
        self.cond = threading.Condition()
        self.slot = None
        self.stop = False
        self.skipped = []                  # frame indices of overwritten (never started) jobs

    def put(self, item):
        with self.cond:
            if self.slot is not None:
                self.skipped.append(self.slot[0])   # previous job never started: overwritten
            self.slot = item
            self.cond.notify()

    def get(self):
        with self.cond:
            while self.slot is None and not self.stop:
                self.cond.wait()
            item, self.slot = self.slot, None
            return item

    def close(self):
        with self.cond:
            self.stop = True
            self.cond.notify_all()


def rta_low(c_low, c_high, t_high, deadline):
    """Response time of the lower-priority task under fixed priorities (uniprocessor):
    R = C_low + ceil(R / T_high) * C_high, iterated to a fixed point. None if R > deadline."""
    r = c_low + c_high
    for _ in range(1000):
        r_new = c_low + math.ceil(r / t_high) * c_high
        if r_new > deadline:
            return None
        if abs(r_new - r) < 1e-9:
            return r_new
        r = r_new
    return None


def stats(a):
    a = np.asarray(a, dtype=float)
    if not len(a):
        return {"n": 0}
    return {"n": int(len(a)), "mean": float(a.mean()), "p50": pct(a, 50), "p99": pct(a, 99), "max": float(a.max())}


def main():
    a = parse_args()
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    cores = {int(c) for c in a.cores.split(",")}
    os.sched_setaffinity(0, cores)              # inherited by every thread created after this
    cv2.setNumThreads(a.cv_threads)
    dec_name, enc_name = CODECS[a.mode]

    packets, params = load_packets(a.input)
    w, h = params["width"], params["height"]
    net = load_detector(a.model_dir)
    period, n_det = 1.0 / a.fps, a.detect_every
    det_period = n_det * period

    mailbox = Mailbox()
    shared = {"boxes": [], "box_frame": -1}
    shared_lock = threading.Lock()
    det_rows = []
    ready = threading.Barrier(2)
    clock = {}

    def detect_task():
        if a.sched == "rms":
            set_fifo(PRIO_DETECT)
        detect(net, np.zeros((h, w, 3), np.uint8), a.conf)       # warm-up (first call is slow)
        ready.wait()
        while True:
            item = mailbox.get()
            if item is None:
                return
            idx, img, release = item
            t_start, c0 = time.perf_counter(), time.thread_time()
            boxes = detect(net, img, a.conf)
            c1, t_end = time.thread_time(), time.perf_counter()
            with shared_lock:
                shared["boxes"], shared["box_frame"] = boxes, idx
            resp = t_end - release
            det_rows.append([idx, round(clock["wall0"] + release - clock["t0"], 6),
                             round((t_start - release) * 1e3, 3), round((c1 - c0) * 1e3, 3),
                             round((t_end - t_start) * 1e3, 3), round(resp * 1e3, 3), int(resp > det_period),
                             sum(1 for b in boxes if b[0] == PERSON)])

    det_thread = threading.Thread(target=detect_task, name="detect", daemon=True)
    det_thread.start()

    if a.sched == "rms":
        set_fifo(PRIO_FRAME)
    dec = open_decoder(dec_name, params, a.codec_threads)      # codec threads inherit this thread's policy
    enc = open_encoder(enc_name, w, h, a.fps, a.bitrate, a.codec_threads)
    src = frame_source(dec, packets)
    for _ in range(3):                                         # prime the decoder
        next(src)
    ready.wait()

    rows = []
    t0 = time.perf_counter()
    clock.update(t0=t0, wall0=time.time())
    i = -1
    while time.perf_counter() - t0 < a.duration:
        i += 1
        release = t0 + i * period
        now = time.perf_counter()
        if now < release:
            time.sleep(release - now)
        ts, c0 = time.perf_counter(), time.thread_time()
        frame = next(src)
        t1 = time.perf_counter()
        img = to_bgr(frame)
        t2 = time.perf_counter()
        handed = (i % n_det == 0)
        if handed:
            mailbox.put((i, img.copy(), release))
        t3 = time.perf_counter()
        with shared_lock:
            boxes, box_frame = shared["boxes"], shared["box_frame"]
        for cls, score, x1, y1, x2, y2 in boxes:
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0) if cls == PERSON else (255, 160, 0), 2)
        t4 = time.perf_counter()
        vf = av.VideoFrame.from_ndarray(img, format="bgr24").reformat(format="yuv420p")
        vf.pts = i
        t5 = time.perf_counter()
        enc_bytes = sum(p.size for p in enc.encode(vf))
        t6, c1 = time.perf_counter(), time.thread_time()
        lat = t6 - release
        rows.append([i, round(clock["wall0"] + release - t0, 6), round(lat * 1e3, 3), int(lat > period),
                     round((t6 - ts) * 1e3, 3), round((c1 - c0) * 1e3, 3),
                     round((t1 - ts) * 1e3, 3), round((t2 - t1) * 1e3, 3), round((t3 - t2) * 1e3, 3),
                     round((t4 - t3) * 1e3, 3), round((t5 - t4) * 1e3, 3), round((t6 - t5) * 1e3, 3),
                     int(handed), i - box_frame if box_frame >= 0 else -1, enc_bytes,
                     read_temp(), read_int(FREQ_PATH)])
    t_end = time.perf_counter()
    mailbox.close()
    det_thread.join(timeout=5)
    for _ in enc.encode(None):
        pass

    with open(out / "frames.csv", "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["frame", "release_wall_s", "latency_ms", "miss", "service_ms", "cpu_ms", "decode_ms",
                     "to_bgr_ms", "handoff_ms", "overlay_ms", "to_yuv_ms", "encode_ms", "handed",
                     "box_age_frames", "enc_bytes", "temp_c", "scaling_cur_freq_khz"])
        wr.writerows(rows)
    with open(out / "detect.csv", "w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["frame", "release_wall_s", "start_delay_ms", "cpu_ms", "wall_ms", "response_ms", "miss", "persons"])
        wr.writerows(det_rows)

    warm_f = int(a.warmup * a.fps)
    fr = np.array([r[2:6] for r in rows[warm_f:]], dtype=float)        # latency, miss, service, cpu
    dr = np.array([r[2:7] for r in det_rows if r[0] >= warm_f], dtype=float) if det_rows else np.zeros((0, 5))
    c_f, c_d = fr[:, 3], (dr[:, 1] if len(dr) else np.array([]))
    jobs_released = len(range(warm_f, len(rows), n_det)) if len(rows) > warm_f else 0

    analysis = {"period_ms": period * 1e3, "detect_period_ms": det_period * 1e3,
                "uniprocessor": len(cores) == 1 and a.cv_threads == 1 and a.codec_threads == 1,
                "ll_bound_2_tasks": LL_BOUND_2}
    if len(c_d):
        for tag, cf, cd in (("mean", c_f.mean(), c_d.mean()), ("max", c_f.max(), c_d.max()),
                            ("p99", pct(c_f, 99), pct(c_d, 99))):
            u = cf / (period * 1e3) + cd / (det_period * 1e3)
            r_det = rta_low(cd, cf, period * 1e3, det_period * 1e3)
            analysis[f"using_C_{tag}"] = {
                "C_frame_ms": cf, "C_detect_ms": cd, "U": u, "U_frame": cf / (period * 1e3),
                "ll_test_passes": bool(u <= LL_BOUND_2),
                "rta_frame_R_ms": cf, "rta_frame_ok": bool(cf <= period * 1e3),
                "rta_detect_R_ms": r_det, "rta_detect_ok": r_det is not None,
            }
    summary = {
        "config": {**vars(a), "decoder": dec_name, "encoder": enc_name, "width": w, "height": h,
                   "cores_list": sorted(cores), "prio_frame": PRIO_FRAME if a.sched == "rms" else None,
                   "prio_detect": PRIO_DETECT if a.sched == "rms" else None},
        "versions": {"python": platform.python_version(), "pyav": av.__version__, "opencv": cv2.__version__,
                     "host": platform.node(), "kernel": platform.release(),
                     "governor": open(GOV_PATH).read().strip() if os.path.exists(GOV_PATH) else None},
        "elapsed_s": t_end - t0, "frames": len(rows), "achieved_fps": len(rows) / (t_end - t0),
        "frame_task": {"miss_ratio": float(fr[:, 1].mean()), "latency_ms": stats(fr[:, 0]),
                       "service_ms": stats(fr[:, 2]), "cpu_ms": stats(c_f),
                       "wall_minus_cpu_ms": stats(fr[:, 2] - fr[:, 3])},
        "detect_task": {"jobs_released": jobs_released, "jobs_completed": int(len(dr)),
                        "jobs_skipped": sum(1 for s in mailbox.skipped if s >= warm_f),
                        "miss_ratio": float(dr[:, 4].mean()) if len(dr) else None,
                        "cpu_ms": stats(c_d), "response_ms": stats(dr[:, 3] if len(dr) else []),
                        "start_delay_ms": stats(dr[:, 0] if len(dr) else [])},
        "analysis": analysis,
        "temp_c": {"start": rows[0][15], "end": rows[-1][15]},
    }
    with open(out / "summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    ft, dt = summary["frame_task"], summary["detect_task"]
    am = analysis.get("using_C_max", {})
    print(f"{a.mode}/{a.sched}: {summary['achieved_fps']:.1f} fps | frame miss {100 * ft['miss_ratio']:.1f}% "
          f"C {ft['cpu_ms'].get('mean', 0):.1f}/{ft['cpu_ms'].get('max', 0):.1f} ms | detect done {dt['jobs_completed']}"
          f"/{dt['jobs_released']} skipped {dt['jobs_skipped']} C {dt['cpu_ms'].get('mean', 0):.0f} ms "
          f"R max {dt['response_ms'].get('max', 0):.0f} ms | U(max C) {am.get('U', float('nan')):.2f}")


if __name__ == "__main__":
    main()
