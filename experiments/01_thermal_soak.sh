#!/usr/bin/env bash
# Experiment 01: thermal soak. Does the board throttle under sustained all-core load?
# Worst case for the pipeline: stress-ng on all 4 cores at the 'performance' governor,
# logging temperature, real ARM clock and throttle flags every second.
# (First run 2026-11-06 used these exact commands typed by hand; this script reproduces it.)
#
# Usage (on the Pi, from the repo root): ./experiments/01_thermal_soak.sh [seconds, default 600]
set -uo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SECS="${1:-600}"
GOV=/sys/devices/system/cpu/cpufreq/policy0/scaling_governor
OUT="$REPO_DIR/data/raw/01_thermal_soak"
mkdir -p "$OUT"
LOG="$OUT/$(date +%Y%m%dT%H%M%S).csv"
"$REPO_DIR/scripts/sysinfo.sh" "${LOG%.csv}.sysinfo.txt" >/dev/null

PREV_GOV=$(cat $GOV)
echo performance | sudo tee $GOV >/dev/null
trap 'echo "$PREV_GOV" | sudo tee $GOV >/dev/null' EXIT

echo "t,temp_C,arm_hz,throttled" > "$LOG"
( for _ in $(seq $((SECS + 60))); do
    echo "$(date +%s),$(vcgencmd measure_temp | grep -oE '[0-9.]+'),$(vcgencmd measure_clock arm | cut -d= -f2),$(vcgencmd get_throttled | cut -d= -f2)"
    sleep 1
  done >> "$LOG" ) &
stress-ng --cpu 4 --timeout "${SECS}s" --metrics-brief
wait

awk -F, 'NR==2 { t0=$1 }
  NR>1 { if ($2>m) m=$2; if (!c || $3<c) c=$3; if (!h && $2>=80) h=$1-t0; if (!d && $3<1790000000) d=$1-t0; t=$4 }
  END { print "max temp:", m, "C | min clock:", c/1e6, "MHz | reached 80 C after:", (h?h" s":"never"),
        "| first clock drop after:", (d?d" s":"never"), "| throttle flags at end:", t }' "$LOG"
echo "Saved to $LOG"
