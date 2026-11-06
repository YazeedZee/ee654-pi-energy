#!/usr/bin/env python3
"""Experiment 03: why is reading hardware-decoded frames slow?

Exp 02 showed to_bgr (colour conversion of each decoded frame) at ~150 ms per frame
after hardware decode vs ~5 ms after software decode. This separates two causes:

  raw_copy   copy the frame's planes into normal memory (pure memory read, no conversion)
  cvt_copy   colour-convert that copy with OpenCV (conversion from normal memory)
  to_ndarray PyAV's direct conversion from the decoder's buffer (what the pipeline does)

If raw_copy is slow too  -> the decoder's buffers are slow for the CPU to read
                            (e.g. uncached memory): a data-movement cost (H1).
If raw_copy is fast      -> the conversion path is the problem; copy-then-convert fixes it.

Usage (on the Pi, from the repo root):
  python3 experiments/03_frame_access.py [input.mp4] [frames, default 150]
Output: data/raw/03_frame_access/<timestamp>/{frames.csv, summary.json, sysinfo.txt}
"""
import csv
import json
import subprocess
import sys
import time
from pathlib import Path

import av
import cv2
import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "pipeline"))
from run_pipeline import load_packets, open_decoder, frame_source  # noqa: E402


def planes_to_array(frame):
    """Copy a yuv420p frame's planes (honouring line padding) into one contiguous I420 array."""
    w, h = frame.width, frame.height
    out = np.empty((h * 3 // 2, w), dtype=np.uint8)
    y = np.frombuffer(frame.planes[0], np.uint8).reshape(-1, frame.planes[0].line_size)[:h, :w]
    out[:h] = y
    cw, ch = w // 2, h // 2
    for k, p in enumerate(frame.planes[1:3]):
        c = np.frombuffer(p, np.uint8).reshape(-1, p.line_size)[:ch, :cw]
        out[h + k * ch // 2: h + (k + 1) * ch // 2] = c.reshape(-1, w)
    return out


def main():
    inp = sys.argv[1] if len(sys.argv) > 1 else str(REPO / "data/inputs/pedestrian_area_720p30.mp4")
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 150
    out = REPO / "data/raw/03_frame_access" / time.strftime("%Y%m%dT%H%M%S")
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run([str(REPO / "scripts/sysinfo.sh"), str(out / "sysinfo.txt")], stdout=subprocess.DEVNULL)

    packets, params = load_packets(inp)
    rows, summary = [], {"input": inp, "frames": n, "pyav": av.__version__, "opencv": cv2.__version__, "modes": {}}

    for mode, dec_name in (("sw", "h264"), ("hw", "h264_v4l2m2m")):
        try:
            dec = open_decoder(dec_name, params)
        except Exception as e:  # noqa: BLE001
            print(f"{mode}: cannot open {dec_name}: {e}")
            summary["modes"][mode] = {"error": str(e)}
            continue
        src = frame_source(dec, packets)
        for _ in range(10):          # warm-up
            next(src)
        fmt = None
        for i in range(n):
            f = next(src)
            fmt = f.format.name
            nbytes = sum(p.buffer_size for p in f.planes)
            first_copy = (i % 2 == 0)        # alternate order so neither method always reads first
            t = {}
            for step in (("copy", "direct") if first_copy else ("direct", "copy")):
                if step == "copy":
                    t0 = time.perf_counter()
                    arr = planes_to_array(f) if fmt == "yuv420p" else None
                    t1 = time.perf_counter()
                    if arr is not None:
                        cv2.cvtColor(arr, cv2.COLOR_YUV2BGR_I420)
                    t2 = time.perf_counter()
                    t["raw_copy"], t["cvt_copy"] = (t1 - t0) * 1e3, (t2 - t1) * 1e3
                else:
                    t0 = time.perf_counter()
                    f.to_ndarray(format="bgr24")
                    t["to_ndarray"] = (time.perf_counter() - t0) * 1e3
            rows.append([mode, i, fmt, nbytes, round(t["raw_copy"], 3), round(t["cvt_copy"], 3), round(t["to_ndarray"], 3)])

        m = [r for r in rows if r[0] == mode]
        med = lambda k: float(np.median([r[k] for r in m]))  # noqa: E731
        raw = med(4)
        summary["modes"][mode] = {
            "decoder": dec_name, "pix_fmt": fmt, "bytes_per_frame": m[0][3],
            "raw_copy_ms": raw, "cvt_copy_ms": med(5), "to_ndarray_ms": med(6),
            "raw_copy_MB_per_s": m[0][3] / 1e6 / (raw / 1e3) if raw > 0 else None,
        }
        s = summary["modes"][mode]
        print(f"{mode}: pix_fmt={fmt}  raw_copy {s['raw_copy_ms']:.2f} ms ({s['raw_copy_MB_per_s']:.0f} MB/s)"
              f"  cvt_copy {s['cvt_copy_ms']:.2f} ms  to_ndarray {s['to_ndarray_ms']:.2f} ms  (medians, {n} frames)")

    with open(out / "frames.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["mode", "frame", "pix_fmt", "bytes", "raw_copy_ms", "cvt_copy_ms", "to_ndarray_ms"])
        w.writerows(rows)
    with open(out / "summary.json", "w") as fh:
        json.dump(summary, fh, indent=2)
    print(f"Saved to {out}")


if __name__ == "__main__":
    main()
