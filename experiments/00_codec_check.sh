#!/usr/bin/env bash
# Experiment 00: does the H.264 hardware codec work, and how does it compare with software?
#
# Functional check plus a first, rough RQ1 data point. NOT paper evidence:
# one run, no power measurement, governor not fixed.
#
# Four runs on 10 s of synthetic 720p30 video (300 frames):
#   hw_enc  h264_v4l2m2m encode      sw_enc  libx264 (veryfast) encode
#   hw_dec  h264_v4l2m2m decode      sw_dec  software decode
# Encode runs include generating the test pattern on the CPU, so their CPU
# figures are an upper bound on the encoder's own cost.
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

echo "run,status,frames,fps,speed,utime_s,stime_s,rtime_s,cpu_cores_used,governor,temp_before_C,temp_after_C,throttled_after" > "$OUT/summary.csv"

run() {
  local name=$1; shift
  local log="$OUT/$name.log" status=ok
  local t0; t0=$(temp)
  echo "== $name"
  ffmpeg -hide_banner -nostdin -benchmark "$@" > "$log" 2>&1 || status=FAILED
  local frames fps speed ut st rt cores
  frames=$(field "$log" frame); fps=$(field "$log" fps); speed=$(field "$log" speed)
  ut=$(bench "$log" utime); st=$(bench "$log" stime); rt=$(bench "$log" rtime)
  cores=$(awk -v u="${ut:-0}" -v s="${st:-0}" -v r="${rt:-0}" 'BEGIN{ if (r>0) printf "%.2f", (u+s)/r }')
  echo "$name,$status,$frames,$fps,$speed,$ut,$st,$rt,$cores,$(cat $GOV_FILE),$t0,$(temp),$(thr)" >> "$OUT/summary.csv"
  [[ $status == ok ]] || echo "   FAILED: see $log"
  sleep 5                              # let temperature settle between runs
}

run hw_enc "${SRC[@]}" -pix_fmt yuv420p -c:v h264_v4l2m2m -b:v 4M -y "$TMP/hw.mp4"
run sw_enc "${SRC[@]}" -c:v libx264 -preset veryfast -b:v 4M -y "$TMP/sw.mp4"
run hw_dec -c:v h264_v4l2m2m -i "$TMP/sw.mp4" -f null -
run sw_dec -i "$TMP/sw.mp4" -f null -

echo
column -s, -t "$OUT/summary.csv"
echo
echo "Saved to $OUT"
echo "cpu_cores_used = (user+system CPU time) / wall time; 4.0 = all four cores busy."
