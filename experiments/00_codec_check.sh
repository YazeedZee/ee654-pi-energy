#!/usr/bin/env bash
# Experiment 00: does the H.264 hardware codec work, and how does it compare with software?
#
# Functional check plus a first, rough RQ1 data point. NOT paper evidence:
# one run, no power measurement, governor not fixed.
#
# Five runs on 10 s of synthetic 720p30 video (300 frames):
#   gen_only  test-pattern generation only (baseline for the encode runs)
#   hw_enc    h264_v4l2m2m encode      sw_enc  libx264 (veryfast) encode
#   hw_dec    h264_v4l2m2m decode      sw_dec  software decode
# Encode runs include generating the test pattern on the CPU; subtract the
# gen_only CPU-seconds to estimate the encoder's own cost (printed at the end).
# fps is computed as frames / wall time: ffmpeg itself reports fps=0 for
# runs shorter than 1 s.
#
# Output: data/raw/00_codec_check/<timestamp>/{sysinfo.txt, <run>.log, summary.csv}
# Usage (on the Pi, from the repo root): ./experiments/00_codec_check.sh
set -uo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$REPO_DIR/data/raw/00_codec_check/$(date +%Y%m%dT%H%M%S)"
mkdir -p "$OUT"
"$REPO_DIR/scripts/sysinfo.sh" "$OUT/sysinfo.txt" >/dev/null

TMP=$(mktemp -d)                       # /tmp is RAM-backed on Raspberry Pi OS (Debian 13)
trap 'rm -rf "$TMP"' EXIT
GOV_FILE=/sys/devices/system/cpu/cpu0/cpufreq/scaling_governor
SRC=(-f lavfi -i testsrc2=size=1280x720:rate=30 -t 10)

temp()  { vcgencmd measure_temp | grep -oE '[0-9.]+'; }
thr()   { vcgencmd get_throttled | cut -d= -f2; }
field() { tr '\r' '\n' < "$1" | grep -E 'frame=' | tail -1 | grep -oE "$2=[[:space:]]*[0-9.]+" | grep -oE '[0-9.]+$'; }
bench() { grep -oE "$2=[0-9.]+" "$1" | grep -oE '[0-9.]+$'; }

echo "run,status,frames,fps_wall,speed,utime_s,stime_s,rtime_s,cpu_s,cpu_cores_used,hw_device,governor,temp_before_C,temp_after_C,throttled_after" > "$OUT/summary.csv"

run() {
  local name=$1; shift
  local log="$OUT/$name.log" status=ok
  local t0; t0=$(temp)
  echo "== $name"
  ffmpeg -hide_banner -nostdin -benchmark "$@" > "$log" 2>&1 || status=FAILED
  local frames fps speed ut st rt cpu cores dev
  frames=$(field "$log" frame); speed=$(field "$log" speed)
  ut=$(bench "$log" utime); st=$(bench "$log" stime); rt=$(bench "$log" rtime)
  fps=$(awk -v f="${frames:-0}" -v r="${rt:-0}" 'BEGIN{ if (r>0) printf "%.1f", f/r }')
  cpu=$(awk -v u="${ut:-0}" -v s="${st:-0}" 'BEGIN{ printf "%.3f", u+s }')
  cores=$(awk -v c="$cpu" -v r="${rt:-0}" 'BEGIN{ if (r>0) printf "%.2f", c/r }')
  dev=$(grep -oE '/dev/video[0-9]+' "$log" | sort -u | paste -sd'+' -); dev=${dev:--}
  echo "$name,$status,$frames,$fps,$speed,$ut,$st,$rt,$cpu,$cores,$dev,$(cat $GOV_FILE),$t0,$(temp),$(thr)" >> "$OUT/summary.csv"
  [[ $status == ok ]] || echo "   FAILED: see $log"
  sleep 5                              # let temperature settle between runs
}

run gen_only "${SRC[@]}" -pix_fmt yuv420p -f null -
run hw_enc "${SRC[@]}" -pix_fmt yuv420p -c:v h264_v4l2m2m -b:v 4M -y "$TMP/hw.mp4"
run sw_enc "${SRC[@]}" -c:v libx264 -preset veryfast -b:v 4M -y "$TMP/sw.mp4"
run hw_dec -c:v h264_v4l2m2m -i "$TMP/sw.mp4" -f null -
run sw_dec -i "$TMP/sw.mp4" -f null -

echo
column -s, -t "$OUT/summary.csv"
echo
echo "Encoder CPU after subtracting test-pattern generation (gen_only):"
awk -F, 'NR>1 { cpu[$1]=$9 } END {
  g = cpu["gen_only"]
  for (r in cpu) if (r ~ /_enc$/) printf "  %-7s %.2f CPU-s total, %.2f CPU-s net of gen_only\n", r, cpu[r], cpu[r]-g
}' "$OUT/summary.csv"
echo
echo "Saved to $OUT"
echo "cpu_cores_used = (user+system CPU time) / wall time; 4.0 = all four cores busy."
echo "hw_device: V4L2 device named in the ffmpeg log ('-' = none, i.e. software path)."
