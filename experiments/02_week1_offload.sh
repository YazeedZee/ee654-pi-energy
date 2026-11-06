#!/usr/bin/env bash
# Experiment 02: week-one feasibility test for RQ1 (offloading under passive cooling).
#
# Runs pipeline v1 in software and hardware mode, sustained, in balanced order
# (sw hw hw sw per repetition) so both modes see a similar thermal history.
# A background sampler logs the real ARM clock, temperature and throttle flags.
#
# Usage (on the Pi, from the repo root):
#   ./experiments/02_week1_offload.sh [input.mp4]
# Environment overrides (defaults in brackets):
#   DURATION [180]  seconds per run      N   [3]   detect every N frames
#   REPS     [1]    sw-hw-hw-sw blocks   GAP [60]  seconds idle between runs
#   SAMPLE   [0.5]  sampler period (s)
# Output: data/raw/02_week1_offload/<timestamp>/{sysinfo.txt, clock.csv, run<k>_<mode>/...}
set -uo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INPUT="${1:-$REPO_DIR/data/inputs/pedestrian_area_720p30.mp4}"
DURATION="${DURATION:-180}"; N="${N:-3}"; REPS="${REPS:-1}"; GAP="${GAP:-60}"; SAMPLE="${SAMPLE:-0.5}"

[[ -f "$INPUT" ]] || { echo "Input not found: $INPUT (run scripts/fetch_inputs.sh)"; exit 1; }
OUT="$REPO_DIR/data/raw/02_week1_offload/$(date +%Y%m%dT%H%M%S)"
mkdir -p "$OUT"
"$REPO_DIR/scripts/sysinfo.sh" "$OUT/sysinfo.txt" >/dev/null
printf 'input=%s\nduration=%s\ndetect_every=%s\nreps=%s\ngap=%s\ninput_sha256=%s\n' \
  "$INPUT" "$DURATION" "$N" "$REPS" "$GAP" "$(sha256sum "$INPUT" | cut -d' ' -f1)" > "$OUT/params.txt"

# Background sampler: real ARM clock (firmware view), temperature, throttle flags
echo "t,arm_hz,temp_c,throttled" > "$OUT/clock.csv"
( while :; do
    echo "$(date +%s.%N),$(vcgencmd measure_clock arm | cut -d= -f2),$(vcgencmd measure_temp | grep -oE '[0-9.]+'),$(vcgencmd get_throttled | cut -d= -f2)"
    sleep "$SAMPLE"
  done >> "$OUT/clock.csv" ) &
SAMPLER=$!
trap 'kill $SAMPLER 2>/dev/null' EXIT

k=0
ORDER=()
for ((r = 0; r < REPS; r++)); do ORDER+=(sw hw hw sw); done
for mode in "${ORDER[@]}"; do
  k=$((k + 1))
  (( k > 1 )) && { echo "-- idle ${GAP}s"; sleep "$GAP"; }
  echo "== run $k/${#ORDER[@]}: $mode (${DURATION}s, detect every $N)"
  python3 "$REPO_DIR/pipeline/run_pipeline.py" --input "$INPUT" --mode "$mode" \
    --duration "$DURATION" --detect-every "$N" --out-dir "$OUT/run${k}_${mode}" \
    || echo "   run $k FAILED"
done

echo
python3 - "$OUT" <<'EOF'
import json, sys, pathlib
out = pathlib.Path(sys.argv[1])
cols = ["decode", "to_bgr", "detect", "overlay", "to_yuv", "encode"]
print(f"{'run':<9}{'fps':>6}{'util':>6}{'miss%':>7}{'svc50':>7}{'svc99':>7}{'cores':>6}{'cpu/f':>7}" + "".join(f"{c:>8}" for c in cols) + f"{'tempC':>13}")
for d in sorted(p for p in out.iterdir() if p.is_dir()):
    f = d / "summary.json"
    if not f.exists():
        print(f"{d.name:<9} (no summary)"); continue
    s = json.load(open(f)); st = s["stages"]
    sv = s["service_ms"]
    print(f"{d.name:<9}{s['achieved_fps']:>6.1f}{s['utilization']:>6.2f}{100*s['miss_ratio']:>7.1f}{sv['p50']:>7.1f}{sv['p99']:>7.1f}"
          f"{s['cpu_cores_used']:>6.2f}{s['cpu_ms_per_frame']:>7.1f}" + "".join(f"{(st[c]['mean_ms'] or 0):>8.1f}" for c in cols)
          + f"{str(round(s['temp_c']['start'] or 0, 1)) + '->' + str(round(s['temp_c']['end'] or 0, 1)):>13}")
EOF
echo
echo "util = mean service time / frame period (>1 = overloaded: cannot keep up; latency then grows without bound)."
echo "svc50/svc99 = per-frame service time (ms, all stages, no waiting). cpu/f = CPU ms per frame, all threads."
echo "Stage columns are mean ms per frame (detect: per detection). Saved to $OUT"
echo "Plot on the PC: python3 analysis/plot_02.py $OUT"
