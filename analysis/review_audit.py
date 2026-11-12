#!/usr/bin/env python3
"""Numbers for the review audit (docs/review_response.md), computed from existing logs only.

Usage (repo root):  python3 analysis/review_audit.py [--root .] > docs/review_audit_numbers.txt

Sections:
  A  Exp 04 job accounting: nominal vs submitted vs completed, on time, after the timed run, submission lag
  B  Exp 04 frame-task blocking evidence: max(start lateness), max(wall - cpu) per frame
  C  Result staleness: box age (frames and ms) on output frames
  D  Actual encoder bitrate from enc_bytes (exp 02 and 04)
  E  Buffer access: same-converter comparison available in existing logs
  F  Governor: per-run summaries treated as the replicates
  G  Run windows (Fig. 3 extent) and exp 02/04 session map
  H  Reconstructed packet-retrieval latency: per-frame packet matching, validated at every key frame
  I  Wall-clock staleness of the boxes drawn on output frames (exp 04)
  J  Equal-work replicates: the eight runs per mode behind Table I
  K  Governor runs: frequency at the start/end of each slow detection frame
  L  Where the hardware encoder's lag grows: position of each later empty call vs key frames and clip loops
"""
import argparse
import csv
import json
import math
from pathlib import Path

import numpy as np


def J(p):
    return json.load(open(p))


def table(p):
    rows = list(csv.DictReader(open(p)))
    def num(v):
        return float(int(v, 16)) if v.startswith("0x") else float(v)
    return {k: np.array([num(r[k]) for r in rows]) for k in rows[0]} if rows else {}


def f(x, d=1):
    return "nan" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.{d}f}"


def exp04(raw):
    print("== A. Exp 04 detection-job accounting (warm-up 3 s excluded; deadline = period = 666.7 ms)")
    hdr = ("run", "fps", "nominal", "submitted", "logged", "overwritten", "completed", "in_run", "after_run",
           "on_time", "unfinished", "R_max_ms", "sublag_p50", "sublag_max", "Cd_mean", "Cd_max")
    print(" ".join(f"{h:>11}" for h in hdr))
    out = {}
    for sess in ("20261110T202628", "20261110T204647"):
        for d in sorted((raw / "04_rms" / sess).iterdir()):
            if not d.is_dir():
                continue
            s = J(d / "summary.json")
            fr, dt = table(d / "frames.csv"), table(d / "detect.csv")
            cfg = s["config"]
            fps, n, dur = cfg["fps"], cfg["detect_every"], cfg["duration"]
            warm = int(cfg["warmup"] * fps)
            period = 1e3 / fps
            nominal = sum(1 for i in range(warm, int(round(dur * fps)) + 1) if i % n == 0)   # releases in [3 s, 90 s]
            wall0 = fr["release_wall_s"][0]
            t_end = wall0 + s["elapsed_s"]
            keep = dt["frame"] >= warm
            done = dt["release_wall_s"][keep] + dt["response_ms"][keep] / 1e3
            in_run = int((done <= t_end).sum())
            on_time = int((dt["response_ms"][keep] <= n * period).sum())
            submitted = int(((fr["handed"] == 1) & (fr["frame"] >= warm)).sum())     # actually handed over
            logged = s["detect_task"]["jobs_released"]                              # summary.json value
            over = s["detect_task"]["jobs_skipped"]
            completed = int(keep.sum())
            # submission time of a handed frame = start of its service + decode + to_bgr + hand-off
            h = (fr["handed"] == 1) & (fr["frame"] >= warm)
            lag = (fr["latency_ms"] - fr["service_ms"] + fr["decode_ms"] + fr["to_bgr_ms"] + fr["handoff_ms"])[h]
            r = dict(fps=s["achieved_fps"], nominal=nominal, submitted=submitted, logged=logged, overwritten=over,
                     completed=completed, in_run=in_run, after_run=completed - in_run, on_time=on_time,
                     unfinished=submitted - over - completed,
                     R_max=float(dt["response_ms"][keep].max()) if completed else float("nan"),
                     sublag_p50=float(np.median(lag)), sublag_max=float(lag.max()),
                     Cd_mean=s["detect_task"]["cpu_ms"].get("mean", float("nan")),
                     Cd_max=s["detect_task"]["cpu_ms"].get("max", float("nan")))
            out[f"{sess}/{d.name}"] = r
            print(f"{d.name:>11.11} " + " ".join(f"{v:>11}" for v in (
                f(r["fps"]), r["nominal"], r["submitted"], r["logged"], r["overwritten"], r["completed"], r["in_run"],
                r["after_run"], r["on_time"], r["unfinished"], f(r["R_max"], 0), f(r["sublag_p50"]),
                f(r["sublag_max"], 0), f(r["Cd_mean"], 0), f(r["Cd_max"], 0))))
    print("nominal = periodic releases in [3 s, 90 s]; submitted = frames actually handed to the detector"
          " (index % N == 0, after warm-up); logged = jobs_released in summary.json (off by one when the"
          " frame count ends on 0..4 mod 10); unfinished = submitted - overwritten - completed;"
          " sublag = ms from nominal release to hand-off\n")

    print("== B. Frame-task blocking evidence (frames after warm-up)")
    print(f"{'run':>24} {'Cf_max':>8} {'start_late_max':>15} {'wall-cpu_p99':>13} {'wall-cpu_max':>13} {'resp_max':>9}")
    for sess in ("20261110T202628", "20261110T204647"):
        for d in sorted((raw / "04_rms" / sess).iterdir()):
            if not d.is_dir():
                continue
            fr = table(d / "frames.csv")
            k = fr["frame"] >= 45
            late = (fr["latency_ms"] - fr["service_ms"])[k]
            wmc = (fr["service_ms"] - fr["cpu_ms"])[k]
            print(f"{d.name:>24} {fr['cpu_ms'][k].max():>8.1f} {late.max():>15.2f} {np.percentile(wmc, 99):>13.2f}"
                  f" {wmc.max():>13.2f} {fr['latency_ms'][k].max():>9.1f}")
    print("start_late = release -> start of service (includes any wait for the GIL or the CPU)\n")

    print("== C. Staleness of boxes drawn on output frames (frames after warm-up with boxes available)")
    print(f"{'run':>24} {'age_p50_fr':>11} {'age_max_fr':>11} {'lag_p50_ms':>11} {'lag_max_ms':>11}")
    for sess in ("20261110T202628", "20261110T204647"):
        for d in sorted((raw / "04_rms" / sess).iterdir()):
            if not d.is_dir():
                continue
            s = J(d / "summary.json")
            fr = table(d / "frames.csv")
            per = 1e3 / s["config"]["fps"]
            k = (fr["frame"] >= 45) & (fr["box_age_frames"] >= 0)
            age = fr["box_age_frames"][k]
            if not len(age):
                print(f"{d.name:>24} {'no boxes during the run':>47}")
                continue
            age_ms = age * per          # content lag: video time between the analysed frame and the shown frame
            print(f"{d.name:>24} {np.median(age):>11.0f} {age.max():>11.0f} {np.median(age_ms):>11.0f} {age_ms.max():>11.0f}"
                  f"   (frames with boxes: {k.sum()}/{(fr['frame'] >= 45).sum()})")
    print()
    return out


def bitrate(raw):
    print("== D. Actual encoder output bitrate (target 4 Mb/s)")
    for sess in ("02_week1_offload/20261107T001714", "02_week1_offload/20261107T003226",
                 "02_week1_offload/20261107T121158", "02_week1_offload/20261107T125426",
                 "02_week1_offload/20261107T130959", "04_rms/20261110T202628"):
        for d in sorted((raw / sess).iterdir()):
            if not d.is_dir() or not (d / "frames.csv").exists():
                continue
            fps = J(d / "summary.json")["config"]["fps"]
            fr = table(d / "frames.csv")
            n = len(fr["frame"])
            mbps = fr["enc_bytes"].sum() * 8 / (n / fps) / 1e6     # stream duration = frames / encoder frame rate
            print(f"{sess.split('/')[-1]}/{d.name:<16} {fps:g} fps, {n:>5} frames: {mbps:5.2f} Mb/s"
                  f" ({fr['enc_bytes'].sum() / n / 1e3:5.1f} kB/frame; packets still in the encoder at stop not counted)")
    print()


def buffer_access(raw):
    print("== E. Buffer access")
    s = J(raw / "03_frame_access/20261106T215616/summary.json")["modes"]
    for m in ("sw", "hw"):
        x = s[m]
        print(f"exp03 {m}: raw copy {x['raw_copy_ms']:.2f}  OpenCV convert {x['cvt_copy_ms']:.2f}"
              f"  copy+OpenCV {x['raw_copy_ms'] + x['cvt_copy_ms']:.2f}  direct swscale {x['to_ndarray_ms']:.2f} ms")
    hw, sw = s["hw"], s["sw"]
    print(f"  hw direct / hw copy+OpenCV = {hw['to_ndarray_ms'] / (hw['raw_copy_ms'] + hw['cvt_copy_ms']):.1f}x;"
          f"  hw direct / sw direct (same converter) = {hw['to_ndarray_ms'] / sw['to_ndarray_ms']:.1f}x")
    print(f"  converter effect on normal memory (sw): swscale direct - (copy+OpenCV) ="
          f" {sw['to_ndarray_ms'] - sw['raw_copy_ms'] - sw['cvt_copy_ms']:.2f} ms")
    sysinfo = (raw / "03_frame_access/20261106T215616/sysinfo.txt").read_text()
    thr = [l for l in sysinfo.splitlines() if l.startswith("throttled=")]
    print(f"  exp03 sysinfo {thr}: bit16 = under-voltage has occurred since boot, bit18 = throttling has occurred")
    for sess, runs in (("04_rms/20261110T202628", ("run1_hw-rms", "run8_hw-rms", "run4_sw-rms", "run5_sw-rms")),):
        for r in runs:
            fr = table(raw / sess / r / "frames.csv")
            k = fr["frame"] >= 45
            print(f"exp04 {r}: to_bgr (copy + swscale, same converter as 'direct') mean {fr['to_bgr_ms'][k].mean():.2f}"
                  f"  p99 {np.percentile(fr['to_bgr_ms'][k], 99):.2f} ms")
    print()


def governor(raw):
    print("== F. Governor runs (exp 02, 20261107T134531): one value per run is the replicate")
    d = raw / "02_week1_offload/20261107T134531"
    pw = {}
    for line in (d / "wall_power.txt").read_text().splitlines():
        if line.startswith("run"):
            k, v = line.split(":", 1)
            pw[k] = np.array([float(x) for x in v.split()])
    clock = table(d / "clock.csv")
    for run in ("run1_hw-ondemand", "run4_hw-ondemand", "run2_hw-performance", "run3_hw-performance"):
        fr = table(d / run / "frames.csv")
        t0 = fr["release_wall_s"][0]
        k = (fr["detected"] == 1) & (fr["release_wall_s"] - t0 > 2)
        v = fr["service_ms"][k]
        t1 = (fr["release_wall_s"] + fr["latency_ms"] / 1e3).max()
        c = (clock["t"] >= t0) & (clock["t"] <= t1)
        low = (clock["arm_hz"][c] < 1.79e9).mean()
        frames_all = fr["service_ms"][fr["release_wall_s"] - t0 > 2]
        print(f"{run:<22} power {pw[run].mean():.2f} W (n={len(pw[run])}, lag-1 autocorr"
              f" {np.corrcoef(pw[run][:-1], pw[run][1:])[0, 1]:+.2f})  det-frame median {np.median(v):.1f}"
              f" p99 {np.percentile(v, 99):.1f} max {v.max():.1f} ms  >145 ms: {(v > 145).sum()}/{len(v)}"
              f"  low-clock samples {100 * low:.0f}%  all-frame miss {100 * fr['miss'][fr['release_wall_s'] - t0 > 2].mean():.1f}%")
    print("  Per-run means: ondemand 5.50, 5.09; performance 5.12, 5.38 W -> n = 2 per arm; the"
          " between-run spread (0.4 W) is larger than the between-arm difference (0.0 W).\n")


def windows(raw):
    print("== G. Run windows (first nominal release -> last frame completion), exp 02 15 fps reference")
    d = raw / "02_week1_offload/20261107T003226"
    for run in ("run1_sw", "run2_hw", "run3_hw", "run4_sw"):
        fr = table(d / run / "frames.csv")
        t0 = fr["release_wall_s"][0]
        t1 = (fr["release_wall_s"] + fr["latency_ms"] / 1e3).max()
        print(f"{run}: {len(fr['frame'])} frames, window {t1 - t0:.1f} s, last nominal release at"
              f" {fr['release_wall_s'][-1] - t0:.1f} s")
    print()


def match_packets(fr, fps, sw):
    """Map each submitted frame k to the encoder call that returned its packet.
    Assumptions: one packet per frame, returned in submission order (no B-frames). Then the k-th call that
    returned output delivered frame k's packet. Validation (hardware encoder): frames k = 0, GOP, 2*GOP, ...
    are key frames, so the call matched to each must return the largest packet among its neighbours; a call
    returning two packets would shift every later match and fail this test from then on."""
    b = fr["enc_bytes"]
    nz = np.where(b > 0)[0]
    gop = int(round(fps))
    keys = [k for k in range(0, len(nz), gop)]
    ok = 0
    for k in keys:
        c = nz[k]
        lo, hi = max(0, c - gop // 2), min(len(b), c + gop // 2 + 1)
        ok += int(b[c] == b[lo:hi].max())
    return nz, len(keys), ok


def codec_latency(raw):
    print("== H. Reconstructed packet-retrieval latency: release of frame k -> end of the encoder call that returned"
          " frame k's packet (matched as in match_packets; warm-up excluded)")
    print("   Retrieval happens only inside a later encode call, so this bounds when the packet existed from above;"
          " it is this application's retrieval latency, not the encoder's processing time.")
    sess = ["02_week1_offload/20261107T001714", "02_week1_offload/20261107T003226", "02_week1_offload/20261107T121158",
            "02_week1_offload/20261107T125426", "02_week1_offload/20261107T130959",
            "04_rms/20261110T202628", "04_rms/20261110T204647"]
    for sname in sess:
        for d in sorted((raw / sname).iterdir()):
            if not d.is_dir() or not (d / "frames.csv").exists():
                continue
            s = J(d / "summary.json")
            fps = s["config"]["fps"]
            per = 1e3 / fps
            fr = table(d / "frames.csv")
            sw = d.name.split("_")[1].startswith("sw")
            nz, nkeys, keys_ok = match_packets(fr, fps, sw)
            warm = int(s["config"].get("warmup", 2) * fps)
            k = np.arange(warm, len(nz))
            c = nz[k]
            lag = c - k
            e2e = lag * per + fr["latency_ms"][c]
            vals, cnt = np.unique(lag, return_counts=True)
            lagtxt = ", ".join(f"{v}: {n}" for v, n in zip(vals, cnt))
            val = "n/a (sw: lag 0 proven)" if sw else f"{keys_ok}/{nkeys} key frames matched"
            print(f"{sname.split('/')[-1]}/{d.name:<18} lag frames [{lagtxt}]  {val}  frame-task p50 {np.median(fr['latency_ms'][warm:]):8.1f}"
                  f"  retrieval p50 {np.median(e2e):8.1f} max {e2e.max():8.1f} ms  over one period {100 * (e2e > per).mean():5.1f}%")
    print("   sw: libx264 (zerolatency) starts at lag 0 (first call returns a packet) and no later call is empty,"
          " so with one packet per frame its lag is 0 for every frame.\n")


def staleness(raw):
    print("== I. Staleness of drawn boxes in wall-clock time: release of the analysed frame -> completion of the"
          " frame task for the frame on which its boxes are drawn")
    for sess in ("20261110T202628", "20261110T204647"):
        for d in sorted((raw / "04_rms" / sess).iterdir()):
            if not d.is_dir():
                continue
            fr = table(d / "frames.csv")
            per = 1e3 / J(d / "summary.json")["config"]["fps"]
            k = (fr["frame"] >= 45) & (fr["box_age_frames"] >= 0)
            if not k.any():
                print(f"{d.name:>24}  no boxes during the run")
                continue
            wc = fr["box_age_frames"][k] * per + fr["latency_ms"][k]
            print(f"{d.name:>24}  content lag p50 {np.median(fr['box_age_frames'][k]) * per:6.0f} ms"
                  f"  wall-clock p50 {np.median(wc):8.0f} max {wc.max():8.0f} ms")
    print()


def equal_work(raw):
    print("== J. Equal-work replicates (pipeline v1, 15 fps, N = 10): runs behind Table I")
    rows = {"sw": [], "hw": []}
    for sname in ("20261107T003226", "20261107T121158", "20261107T125426", "20261107T130959"):
        for d in sorted((raw / "02_week1_offload" / sname).iterdir()):
            if not d.is_dir():
                continue
            s = J(d / "summary.json")
            m = d.name.split("_")[1]
            rows[m].append((sname, d.name, s["achieved_fps"], s["cpu_cores_used"], s["cpu_ms_per_frame"],
                            s["utilization"], s["miss_ratio"]))
    for m, rr in rows.items():
        for r in rr:
            print(f"  {m} {r[0]}/{r[1]:<8} fps {r[2]:.3f} cores {r[3]:.4f} cpu/frame {r[4]:.2f} ms"
                  f" load factor {r[5]:.4f} miss {100 * r[6]:.1f}%")
        a = np.array([r[2:] for r in rr])
        spread = 100 * (a.max(0) - a.min(0)) / a.min(0)
        print(f"  {m}: {len(rr)} runs; spread (max-min)/min: fps {spread[0]:.2f}%, cores {spread[1]:.2f}%,"
              f" cpu/frame {spread[2]:.2f}%, load factor {spread[3]:.2f}%")
    print()


def governor_freq(raw):
    print("== K. Governor runs: cpufreq frequency logged at the end of the previous frame and of the frame itself,"
          " for detection frames > 145 ms (frame-boundary samples only)")
    d = raw / "02_week1_offload/20261107T134531"
    for run in ("run1_hw-ondemand", "run4_hw-ondemand", "run2_hw-performance", "run3_hw-performance"):
        fr = table(d / run / "frames.csv")
        t0 = fr["release_wall_s"][0]
        idx = np.where((fr["detected"] == 1) & (fr["release_wall_s"] - t0 > 2))[0]
        f_start = fr["scaling_cur_freq_khz"][idx - 1]
        f_end = fr["scaling_cur_freq_khz"][idx]
        v = fr["service_ms"][idx]
        low = (f_start < 1.8e6) | (f_end < 1.8e6)
        slow = v > 145
        detail = ", ".join(f"{a:.1f} ms @ {b / 1e3:.0f}/{c / 1e3:.0f} MHz" for a, b, c in
                           sorted(zip(v[slow], f_start[slow], f_end[slow]), reverse=True))
        print(f"  {run:<20} detection frames {len(idx)}, at low clock {low.sum()} (median {np.median(v[low]) if low.any() else float('nan'):.1f}"
              f" vs {np.median(v[~low]):.1f} ms); >145 ms: {slow.sum()} [{detail}]")
    print()


def lag_changes(raw):
    print("== L. Hardware encoder: later empty calls (lag grows by one) relative to encoder key frames (every GOP)"
          " and to the 375-frame input loop")
    for d in sorted((raw / "02_week1_offload").glob("20261107T*/run*_hw")) + sorted((raw / "04_rms").glob("2026111*/run*hw*")):
        fr = table(d / "frames.csv")
        fps = J(d / "summary.json")["config"]["fps"]
        gop = int(round(fps))
        b = fr["enc_bytes"]
        lead = int(np.argmax(b > 0))
        emp = (np.where(b[lead:] == 0)[0] + lead).tolist()
        desc = ", ".join(f"call {i} (call - last key frame = {i % gop}; frames after loop start = {i % 375})" for i in emp)
        print(f"  {d.parent.name}/{d.name:<18} {fps:g} fps: {desc if emp else 'none'}")
    print()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=".")
    raw = Path(p.parse_args().root) / "data/raw"
    exp04(raw)
    bitrate(raw)
    buffer_access(raw)
    governor(raw)
    windows(raw)
    codec_latency(raw)
    staleness(raw)
    equal_work(raw)
    governor_freq(raw)
    lag_changes(raw)


if __name__ == "__main__":
    main()
