#!/usr/bin/env python3
"""Per-run clock and throttle check for an experiment-02 result folder.

Splits clock.csv by each run's time window (from frames.csv), so idle gaps between runs,
where the governor lowers the clock on purpose, are excluded. For each run reports the ARM
clock range and how many samples had a throttle condition active *at that moment*:
  bit 0 under-voltage now      bit 1 ARM frequency capped now
  bit 2 throttled now          bit 3 soft temperature limit active now
(get_throttled bits 16-19 are 'has occurred since boot' and are sticky, so they cannot
say *when* something happened; bits 0-3 can.)

Window = first frame release to last frame completion (release + latency), so overloaded
runs are checked over their full wall-clock length. (Before 2026-11-07 the window ended at
the last *scheduled* release, which cut overloaded runs short.)

Usage: python3 analysis/clock_check.py data/raw/02_week1_offload/<timestamp>
"""
import csv
import sys
from pathlib import Path

NOW_BITS = {0: "undervolt", 1: "freq_cap", 2: "throttled", 3: "soft_temp"}


def main(d):
    d = Path(d)
    clock = []
    with open(d / "clock.csv") as f:
        for r in csv.DictReader(f):
            try:
                clock.append((float(r["t"]), int(r["arm_hz"]), float(r["temp_c"]), int(r["throttled"], 16)))
            except (ValueError, KeyError):
                continue
    print(f"{'run':<10}{'samples':>8}{'clk min':>9}{'clk med':>9}{'clk max':>9}{'temp max':>9}  active-now counts")
    for rd in sorted(p for p in d.iterdir() if p.is_dir() and (p / "frames.csv").exists()):
        with open(rd / "frames.csv") as f:
            fr = [(float(r["release_wall_s"]), float(r["latency_ms"])) for r in csv.DictReader(f)]
        t0 = fr[0][0]
        t1 = max(rel + lat / 1e3 for rel, lat in fr)
        s = [c for c in clock if t0 <= c[0] <= t1]
        if not s:
            print(f"{rd.name:<10} no clock samples in window"); continue
        clk = sorted(c[1] / 1e6 for c in s)
        counts = {name: sum(1 for c in s if c[3] >> bit & 1) for bit, name in NOW_BITS.items()}
        active = ", ".join(f"{k} {v}" for k, v in counts.items() if v) or "none"
        print(f"{rd.name:<10}{len(s):>8}{clk[0]:>9.0f}{clk[len(clk) // 2]:>9.0f}{clk[-1]:>9.0f}"
              f"{max(c[2] for c in s):>9.1f}  {active}")
    gaps = [c for c in clock if c[3] & 0x1]
    if gaps:
        print(f"\nUnder-voltage active in {len(gaps)} samples overall (including idle gaps).")
    print(f"Sticky flags at end of log: {hex(clock[-1][3]) if clock else 'n/a'}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
