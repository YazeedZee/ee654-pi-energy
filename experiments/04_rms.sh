#!/usr/bin/env bash
# Experiment 04: pipeline v2 as a two-task rate-monotonic system on one CPU core.
#
# Frame task (period 1/FPS) at higher priority than the detect task (period N/FPS).
# Compares normal Linux scheduling (cfs) with real-time RM priorities (rms), in sw and hw mode.
# Each run's summary.json holds measured C, the Liu & Layland utilization test, and
# response-time analysis (RTA) predictions to compare with measured response times and misses.
#
# Usage (on the Pi, from the repo root; needs rtprio, see scripts/setup_pi.sh):
#   ./experiments/04_rms.sh [input.mp4]
# Environment overrides (defaults in brackets):
#   RUNS ["hw:rms hw:cfs sw:cfs sw:rms sw:rms sw:cfs hw:cfs hw:rms"]   mode:sched tokens, balanced order
#   DURATION [90]  FPS [15]  N [10]  CORES [3]  GAP [30]  SAMPLE [0.5]
#   BG [0]   background load: number of CPU-bound stress-ng workers pinned to the same CORES during
#            each run (normal priority, SCHED_OTHER). Run folders then end in -bg<BG>.
# Note: 'cfs' means SCHED_OTHER, Linux's default policy; on kernel >= 6.6 it is implemented by EEVDF.
# Output: data/raw/04_rms/<timestamp>/{sysinfo.txt, params.txt, clock.csv, run<k>_<mode>-<sched>/...}
set -uo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
INPUT="${1:-$REPO_DIR/data/inputs/pedestrian_area_720p30.mp4}"
RUNS="${RUNS:-hw:rms hw:cfs sw:cfs sw:rms sw:rms sw:cfs hw:cfs hw:rms}"
DURATION="${DURATION:-90}"; FPS="${FPS:-15}"; N="${N:-10}"; CORES="${CORES:-3}"; GAP="${GAP:-30}"; SAMPLE="${SAMPLE:-0.5}"; BG="${BG:-0}"

[[ -f "$INPUT" ]] || { echo "Input not found: $INPUT (run scripts/fetch_inputs.sh)"; exit 1; }
if [[ "$RUNS" == *rms* && $EUID -ne 0 && "$(ulimit -r)" == "0" ]]; then
  echo "No rtprio permission (ulimit -r = 0). Run: sudo ./scripts/setup_pi.sh, then log out and back in."; exit 1
fi
OUT="$REPO_DIR/data/raw/04_rms/$(date +%Y%m%dT%H%M%S)"
mkdir -p "$OUT"
"$REPO_DIR/scripts/sysinfo.sh" "$OUT/sysinfo.txt" >/dev/null
printf 'input=%s\nruns=%s\nduration=%s\nfps=%s\ndetect_every=%s\ncores=%s\ngap=%s\nbg=%s\ninput_sha256=%s\n' \
  "$INPUT" "$RUNS" "$DURATION" "$FPS" "$N" "$CORES" "$GAP" "$BG" "$(sha256sum "$INPUT" | cut -d' ' -f1)" > "$OUT/params.txt"

echo "t,arm_hz,temp_c,throttled" > "$OUT/clock.csv"
( while :; do
    echo "$(date +%s.%N),$(vcgencmd measure_clock arm | cut -d= -f2),$(vcgencmd measure_temp | grep -oE '[0-9.]+'),$(vcgencmd get_throttled | cut -d= -f2)"
    sleep "$SAMPLE"
  done >> "$OUT/clock.csv" ) &
SAMPLER=$!
BGPID=""
trap 'kill $SAMPLER 2>/dev/null; [[ -n "$BGPID" ]] && kill $BGPID 2>/dev/null' EXIT

read -ra ORDER <<< "$RUNS"
k=0
for tok in "${ORDER[@]}"; do
  k=$((k + 1)); mode=${tok%%:*}; sched=${tok#*:}
  (( k > 1 )) && { echo "-- idle ${GAP}s"; sleep "$GAP"; }
  name="run${k}_${mode}-${sched}"; (( BG > 0 )) && name="${name}-bg${BG}"
  echo "== run $k/${#ORDER[@]}: $mode, $sched (${DURATION}s, ${FPS} fps, detect every $N, cores $CORES, background $BG)"
  if (( BG > 0 )); then
    taskset -c "$CORES" stress-ng --cpu "$BG" --timeout "$((${DURATION%.*} + 10))s" --quiet &
    BGPID=$!; sleep 2
  fi
  python3 "$REPO_DIR/pipeline/run_pipeline_v2.py" --input "$INPUT" --mode "$mode" --sched "$sched" \
    --duration "$DURATION" --fps "$FPS" --detect-every "$N" --cores "$CORES" \
    --out-dir "$OUT/$name" || echo "   run $k FAILED"
  if [[ -n "$BGPID" ]]; then kill $BGPID 2>/dev/null; wait $BGPID 2>/dev/null; BGPID=""; fi
done

echo
python3 - "$OUT" <<'EOF'
import json, sys, pathlib
out = pathlib.Path(sys.argv[1])
hdr = ["run", "fps", "frMiss%", "Cf mean", "Cf max", "Uf", "Cd mean", "Cd max", "Rd meas", "Rd pred", "dMiss%", "skip", "U(max)", "LL", "RTA"]
print(f"{hdr[0]:<20}" + "".join(f"{h:>9}" for h in hdr[1:]))
for d in sorted(p for p in out.iterdir() if p.is_dir()):
    f = d / "summary.json"
    if not f.exists():
        print(f"{d.name:<20} (no summary)"); continue
    s = json.load(open(f)); ft, dt = s["frame_task"], s["detect_task"]; am = s["analysis"].get("using_C_max", {})
    rp = am.get("rta_detect_R_ms")
    vals = [f"{s['achieved_fps']:.1f}", f"{100*ft['miss_ratio']:.1f}", f"{ft['cpu_ms'].get('mean',0):.1f}", f"{ft['cpu_ms'].get('max',0):.1f}",
            f"{am.get('U_frame',float('nan')):.2f}", f"{dt['cpu_ms'].get('mean',0):.0f}", f"{dt['cpu_ms'].get('max',0):.0f}",
            f"{dt['response_ms'].get('max',0):.0f}", f"{rp:.0f}" if rp else "unsched",
            f"{100*(dt['miss_ratio'] or 0):.1f}", f"{dt['jobs_skipped']}", f"{am.get('U',float('nan')):.2f}",
            "pass" if am.get("ll_test_passes") else "fail", "ok" if am.get("rta_detect_ok") and am.get("rta_frame_ok") else "fail"]
    print(f"{d.name:<20}" + "".join(f"{v:>9}" for v in vals))
EOF
echo
echo "Cf/Cd = CPU time per job (ms) of frame / detect task. Uf = Cf max / frame period."
echo "Rd meas = worst measured detection response; Rd pred = RTA prediction with max C (valid for rms on 1 core)."
echo "U(max) = utilization with max C; LL = Liu & Layland test (U <= 0.828); RTA = both tasks meet deadlines in analysis."
echo "Saved to $OUT"
