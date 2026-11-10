#!/usr/bin/env python3
"""Generate the paper's figures (PDF, vector) from the logged data.

Usage (from the repo root):  python3 analysis/paper_figures.py [--root .] [--out paper/figs]
Every number drawn here comes from data/raw/; the run folders used are listed in RUNS.
"""
import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

RUNS = {
    "ref15": "02_week1_offload/20261107T003226",      # fan on, 15 fps, N = 10 (equal work)
    "frame_access": "03_frame_access/20261106T215616",
    "governor": "02_week1_offload/20261107T134531",   # hw, 15 fps, ondemand vs performance
    "sched_bg": "04_rms/20261110T204647",             # one core, hw, 2 background CPU hogs
}
SW, HW = "#eb6834", "#2a78d6"          # categorical slots 2 / 1 (validated pair)
FIXED, DEFAULT = "#6250d6", "#1baf7a"  # fixed clock / RM priority vs default policy (validated pair)
INK, INK2, GRID = "#0b0b0b", "#52514e", "#d9d8d4"

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "Nimbus Roman", "STIXGeneral", "DejaVu Serif"],
    "mathtext.fontset": "stix", "font.size": 8, "axes.titlesize": 8, "axes.labelsize": 8,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7, "axes.edgecolor": INK2,
    "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2, "axes.linewidth": 0.6,
    "axes.spines.top": False, "axes.spines.right": False, "pdf.fonttype": 42, "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02, "lines.linewidth": 1.2, "legend.frameon": False,
})
COL_W = 3.45  # IEEE column width, inches


def J(p):
    return json.load(open(p))


def rows(p):
    return list(csv.DictReader(open(p)))


def grid(ax, axis="y"):
    ax.grid(axis=axis, color=GRID, lw=0.5)
    ax.set_axisbelow(True)


def fig_stages(raw, out):
    d = raw / RUNS["ref15"]
    stages = [("decode", "Decode"), ("to_bgr", "To BGR"), ("detect", "Detect$^{*}$"),
              ("overlay", "Overlay"), ("to_yuv", "To YUV"), ("encode", "Encode")]
    mean = {}
    for mode, runs in (("sw", ["run1_sw", "run4_sw"]), ("hw", ["run2_hw", "run3_hw"])):
        mean[mode] = [np.mean([J(d / r / "summary.json")["stages"][k]["mean_ms"] for r in runs]) for k, _ in stages]
    fig, ax = plt.subplots(figsize=(COL_W, 1.85))
    y = np.arange(len(stages))
    h = 0.36
    for off, mode, c, lab in ((-h / 2, "sw", SW, "Software codec"), (h / 2, "hw", HW, "Hardware codec")):
        ax.barh(y + off, mean[mode], height=h - 0.04, color=c, label=lab)
        for yi, v in zip(y, mean[mode]):
            ax.text(v * 1.12, yi + off, f"{v:.1f}" if v < 100 else f"{v:.0f}", va="center", fontsize=6.5, color=INK)
    ax.set_xscale("log")
    ax.set_xlim(0.2, 600)
    ax.set_yticks(y, [s for _, s in stages])
    ax.invert_yaxis()
    ax.set_xlabel("Mean time per frame (ms, log scale)")
    grid(ax, "x")
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=2)
    fig.savefig(out / "stages.pdf")
    plt.close(fig)
    return {m: dict(zip([k for k, _ in stages], v)) for m, v in mean.items()}


def fig_frame_access(raw, out):
    s = J(raw / RUNS["frame_access"] / "summary.json")["modes"]
    labels = ["Bulk copy", "Convert\nthe copy", "Copy +\nconvert", "Direct\nconversion"]
    val = {m: [s[m]["raw_copy_ms"], s[m]["cvt_copy_ms"], s[m]["raw_copy_ms"] + s[m]["cvt_copy_ms"],
               s[m]["to_ndarray_ms"]] for m in ("sw", "hw")}
    fig, ax = plt.subplots(figsize=(COL_W, 1.75))
    x = np.arange(len(labels))
    w = 0.36
    for off, m, c, lab in ((-w / 2, "sw", SW, "After software decode"), (w / 2, "hw", HW, "After hardware decode")):
        ax.bar(x + off, val[m], width=w - 0.04, color=c, label=lab)
        for xi, v in zip(x, val[m]):
            ax.text(xi + off, v * 1.15, f"{v:.1f}" if v < 100 else f"{v:.0f}", ha="center", fontsize=6.5, color=INK)
    ax.set_yscale("log")
    ax.set_ylim(0.5, 600)
    ax.set_xticks(x, labels)
    ax.set_ylabel("Time per 720p frame (ms)")
    grid(ax)
    ax.legend(loc="upper left")
    fig.savefig(out / "frame_access.pdf")
    plt.close(fig)
    return val


def fig_governor(raw, out):
    d = raw / RUNS["governor"]
    fig, ax = plt.subplots(figsize=(COL_W, 1.75))
    res = {}
    for run, c, ls in (("run1_hw-ondemand", DEFAULT, "-"), ("run4_hw-ondemand", DEFAULT, "--"),
                       ("run2_hw-performance", FIXED, "-"), ("run3_hw-performance", FIXED, "--")):
        f = rows(d / run / "frames.csv")
        t0 = float(f[0]["release_wall_s"])
        v = np.sort([float(r["service_ms"]) for r in f
                     if r["detected"] == "1" and float(r["release_wall_s"]) - t0 > 2])
        res[run] = {"n": int(len(v)), "median": float(np.median(v)), "max": float(v.max()),
                    "over145": int((v > 145).sum())}
        ax.step(v, np.arange(1, len(v) + 1) / len(v), where="post", color=c, ls=ls, lw=1.1)
    ax.set_xlim(115, 180)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("Service time of frames with detection (ms)")
    ax.set_ylabel("Fraction of frames")
    grid(ax, "both")
    ax.text(146.5, 0.55, "performance\n(fixed 1.8 GHz)", color=FIXED, fontsize=7, ha="left")
    ax.text(152, 0.78, "ondemand", color=DEFAULT, fontsize=7, ha="left")
    ax.annotate("", xy=(173.5, 0.985), xytext=(162, 0.82), arrowprops=dict(arrowstyle="->", color=DEFAULT, lw=0.6))
    fig.savefig(out / "governor.pdf")
    plt.close(fig)
    return res


def fig_temperature(raw, out):
    d = raw / RUNS["ref15"]
    clock = rows(d / "clock.csv")
    fig, ax = plt.subplots(figsize=(COL_W, 1.55))
    res = {}
    for run, c, lab in (("run3_hw", HW, "Hardware codec"), ("run4_sw", SW, "Software codec")):
        f = rows(d / run / "frames.csv")
        t0 = float(f[0]["release_wall_s"])
        t1 = max(float(r["release_wall_s"]) + float(r["latency_ms"]) / 1e3 for r in f)
        pts = [(float(r["t"]) - t0, float(r["temp_c"])) for r in clock if t0 <= float(r["t"]) <= t1]
        t, temp = np.array(pts).T
        k = 9
        sm = np.convolve(temp, np.ones(k) / k, mode="valid")
        ax.plot(t[k // 2: -(k // 2)], sm, color=c)
        ax.text(t[-1] + 3, sm[-1], lab, color=c, fontsize=7, va="center")
        res[run] = {"start": float(temp[:5].mean()), "end": float(temp[-5:].mean())}
    ax.set_xlim(0, 235)
    ax.set_xlabel("Time in run (s)")
    ax.set_ylabel("SoC temp. (°C)")
    grid(ax)
    fig.savefig(out / "temperature.pdf")
    plt.close(fig)
    return res


def fig_sched(raw, out):
    d = raw / RUNS["sched_bg"]
    fig, ax = plt.subplots(figsize=(COL_W, 1.75))
    res = {}
    for run, c, lab in (("run2_hw-cfs-bg2", DEFAULT, "Default policy (SCHED_OTHER)"),
                        ("run1_hw-rms-bg2", FIXED, "Rate-monotonic (SCHED_FIFO)")):
        f = rows(d / run / "frames.csv")
        t0 = float(f[0]["release_wall_s"])
        t = np.array([float(r["release_wall_s"]) + float(r["latency_ms"]) / 1e3 - t0 for r in f])
        lat = np.array([float(r["latency_ms"]) for r in f])
        ax.plot(t, lat, color=c, lw=0.9, label=lab)
        res[run] = {"p99": float(np.percentile(lat[45:], 99)), "max": float(lat.max())}
    ax.axhline(1000 / 15, color=INK2, ls=":", lw=0.8)
    ax.text(2, 1000 / 15 * 1.25, "deadline 66.7 ms", color=INK2, fontsize=6.5)
    ax.set_yscale("log")
    ax.set_ylim(8, 20000)
    ax.set_xlim(0, 92)
    ax.set_xlabel("Time in run (s)")
    ax.set_ylabel("Frame response time (ms)")
    grid(ax)
    ax.legend(loc="upper left")
    fig.savefig(out / "sched_bg.pdf")
    plt.close(fig)
    return res


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--root", default=".")
    p.add_argument("--out", default="paper/figs")
    a = p.parse_args()
    raw = Path(a.root) / "data/raw"
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    numbers = {"stages_15fps": fig_stages(raw, out), "frame_access": fig_frame_access(raw, out),
               "governor": fig_governor(raw, out), "temperature_15fps": fig_temperature(raw, out),
               "sched_bg": fig_sched(raw, out)}
    with open(out / "figure_numbers.json", "w") as f:
        json.dump(numbers, f, indent=2)
    print(json.dumps(numbers, indent=1))


if __name__ == "__main__":
    main()
