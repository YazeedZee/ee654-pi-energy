#!/usr/bin/env python3
"""Plot experiment 02: per-frame latency and stage times over each run, with the ARM clock.

Usage (on the PC, from the repo root):
  python3 analysis/plot_02.py data/raw/02_week1_offload/<timestamp>
Writes <timestamp>/plot_02.png. Needs pandas and matplotlib.

What to look for (plan §7 decision rule): in sustained software runs, does per-frame
time grow when the ARM clock drops, while hardware runs stay flat?

Time axis = when each frame finished (release + latency), so overloaded runs show their
full wall-clock length. Rolling means use fixed time windows, not frame counts.
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
        t = f["release_wall_s"] + f["latency_ms"] / 1e3 - t0      # completion time in run
        t_end = t.iloc[-1]
        deadline = s["deadline_ms"]
        tidx = pd.to_timedelta(t, unit="s")

        def roll(series, mask=None, window="2s", how="mean"):
            sel = series if mask is None else series[mask]
            idx = tidx if mask is None else tidx[mask]
            r = pd.Series(sel.values, index=idx).rolling(window)
            out = r.median() if how == "median" else r.mean()
            return out.index.total_seconds(), out.values

        ax = axes[0, col]
        ax.plot(t, f["service_ms"], lw=0.5, color=MODE_COLOR.get(mode, "k"))
        ax.plot(*roll(f["service_ms"], window="1s", how="median"), lw=1.5, color="k", label="1 s rolling median")
        ax.axhline(deadline, ls="--", color="grey", lw=1, label=f"frame period {deadline:.1f} ms")
        ax.set_title(f"{rd.name}  util {s['utilization']:.2f}  miss {100 * s['miss_ratio']:.1f}%", fontsize=9)
        if col == 0:
            ax.set_ylabel("service time per frame (ms)")
            ax.legend(fontsize=7, loc="upper left")

        ax = axes[1, col]
        det = f["detected"] == 1
        warm = t >= s["config"]["warmup"]          # same warm-up the summary stats exclude
        for st in STAGES:
            if st == "detect_ms":
                x, y = roll(f[st], det & warm, window="10s")
            else:
                x, y = roll(f[st], ~det & warm, window="2s")
            ax.plot(x, y, lw=1, label=st.replace("_ms", ""))
        ax.set_yscale("log")
        if col == 0:
            ax.set_ylabel("stage time (ms, log), after warm-up\n2 s mean; detect 10 s mean")
            ax.legend(fontsize=7, ncol=2, loc="upper left")

        ax = axes[2, col]
        if clock is not None:
            c = clock[(clock["t"] >= t0) & (clock["t"] <= t0 + t_end)]
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
