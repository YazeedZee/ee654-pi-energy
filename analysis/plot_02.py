#!/usr/bin/env python3
"""Plot experiment 02: per-frame latency and stage times over each run, with the ARM clock.

Usage (on the PC, from the repo root):
  python3 analysis/plot_02.py data/raw/02_week1_offload/<timestamp>
Writes <timestamp>/plot_02.png. Needs pandas and matplotlib.

What to look for (plan §7 decision rule): in sustained software runs, does per-frame
time grow when the ARM clock drops, while hardware runs stay flat?
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

MODE_COLOR = {"sw": "#c0392b", "hw": "#2471a3"}
STAGES = ["decode_ms", "to_bgr_ms", "detect_ms", "overlay_ms", "to_yuv_ms", "encode_ms"]


def main(run_dir):
    run_dir = Path(run_dir)
    runs = sorted(p for p in run_dir.iterdir() if p.is_dir() and (p / "frames.csv").exists())
    if not runs:
        sys.exit(f"No runs with frames.csv in {run_dir}")
    clock = pd.read_csv(run_dir / "clock.csv") if (run_dir / "clock.csv").exists() else None

    fig, axes = plt.subplots(3, len(runs), figsize=(4.2 * len(runs), 8.5), sharey="row", squeeze=False)
    for col, rd in enumerate(runs):
        mode = rd.name.split("_")[-1]
        f = pd.read_csv(rd / "frames.csv")
        s = json.load(open(rd / "summary.json"))
        t0 = f["release_wall_s"].iloc[0]
        t = f["release_wall_s"] - t0
        deadline = s["deadline_ms"]

        ax = axes[0, col]
        ax.plot(t, f["latency_ms"], lw=0.5, color=MODE_COLOR.get(mode, "k"))
        ax.plot(t, f["latency_ms"].rolling(30, min_periods=1).median(), lw=1.5, color="k", label="1 s median")
        ax.axhline(deadline, ls="--", color="grey", lw=1, label=f"deadline {deadline:.1f} ms")
        ax.set_title(f"{rd.name}  miss {100 * s['miss_ratio']:.1f}%")
        if col == 0:
            ax.set_ylabel("frame latency (ms)")
            ax.legend(fontsize=7, loc="upper left")

        ax = axes[1, col]
        nondet = f[f["detected"] == 0]
        for st in STAGES:
            if st == "detect_ms":
                series = f.loc[f["detected"] == 1, st]
                tt = t[f["detected"] == 1]
            else:
                series, tt = nondet[st], t[f["detected"] == 0]
            ax.plot(tt, series.rolling(30, min_periods=1).mean(), lw=1, label=st.replace("_ms", ""))
        ax.set_yscale("log")
        if col == 0:
            ax.set_ylabel("stage time, 1 s mean (ms, log)")
            ax.legend(fontsize=7, ncol=2, loc="upper left")

        ax = axes[2, col]
        if clock is not None:
            c = clock[(clock["t"] >= t0) & (clock["t"] <= f["release_wall_s"].iloc[-1])]
            ax.plot(c["t"] - t0, c["arm_hz"] / 1e6, color="k", lw=1.2, label="ARM clock")
            ax2 = ax.twinx()
            ax2.plot(c["t"] - t0, c["temp_c"], color="#e67e22", lw=1, label="temp")
            ax2.set_ylim(30, 90)
            if col == len(runs) - 1:
                ax2.set_ylabel("temperature (°C)", color="#e67e22")
        ax.set_ylim(0, 2000)
        ax.set_xlabel("time in run (s)")
        if col == 0:
            ax.set_ylabel("ARM clock (MHz)")

    fig.suptitle(f"Experiment 02: {run_dir.name}", fontsize=11)
    fig.tight_layout()
    out = run_dir / "plot_02.png"
    fig.savefig(out, dpi=130)
    print(out)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
