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
print(f"{'run':<9}{'fps':>6}{'miss%':>7}{'p50ms':>7}{'p99ms':>7}{'cores':>7}{'cpu ms/f':>9}{'decode':>8}{'detect':>8}{'encode':>8}{'tempC':>12}")
for d in sorted(p for p in out.iterdir() if p.is_dir()):
    f = d / "summary.json"
    if not f.exists():
        print(f"{d.name:<9} (no summary)"); continue
    s = json.load(open(f)); st = s["stages"]
    print(f"{d.name:<9}{s['achieved_fps']:>6.1f}{100*s['miss_ratio']:>7.1f}{s['latency_ms']['p50']:>7.1f}{s['latency_ms']['p99']:>7.1f}"
          f"{s['cpu_cores_used']:>7.2f}{s['cpu_ms_per_frame']:>9.1f}{st['decode']['mean_ms']:>8.1f}{st['detect']['mean_ms']:>8.1f}"
          f"{st['encode']['mean_ms']:>8.1f}{str(s['temp_c']['start'])+'->'+str(s['temp_c']['end']):>12}")
EOF
echo
echo "Stage columns are mean ms per frame (detect: per detection). Saved to $OUT"
echo "Plot on the PC: python3 analysis/plot_02.py $OUT"
