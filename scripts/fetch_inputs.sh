#!/usr/bin/env bash
# Download the Xiph test clips and prepare the H.264 inputs used by the experiments.
# Run on the Pi from the repo root. Needs ~3 GB free temporarily; the raw .y4m files
# are deleted afterwards. Encoding settings are fixed here so inputs are reproducible.
#
#   pedestrian_area  1080p, people walking, low camera motion  (375 frames)
#   crowd_run        1080p, large crowd running, high motion    (500 frames)
#
# Each clip is re-timed to 30 fps (frames are reused as-is, none dropped or added)
# and encoded at 1080p and 720p: H.264 High, CRF 20, 1-second GOP.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
IN="$REPO_DIR/data/inputs"
RAW="$IN/raw"
BASE=https://media.xiph.org/video/derf/y4m
mkdir -p "$RAW"

for clip in pedestrian_area_1080p25 crowd_run_1080p50; do
  name="${clip%_1080p*}"
  y4m="$RAW/$clip.y4m"
  if [[ ! -f "$IN/${name}_720p30.mp4" || ! -f "$IN/${name}_1080p30.mp4" ]]; then
    [[ -f "$y4m" ]] || curl -fL --retry 3 -o "$y4m" "$BASE/$clip.y4m"
    echo "$(sha256sum "$y4m" | cut -d' ' -f1)  $clip.y4m" >> "$IN/SOURCES.sha256"
    for res in 1080 720; do
      out="$IN/${name}_${res}p30.mp4"
      [[ -f "$out" ]] && continue
      echo "== encoding $out"
      ffmpeg -hide_banner -loglevel error -y -r 30 -i "$y4m" \
        -vf "scale=-2:${res}" -c:v libx264 -preset slow -crf 20 \
        -profile:v high -level 4.1 -pix_fmt yuv420p -g 30 -an "$out"
    done
    rm -f "$y4m"
  fi
done

cd "$IN"
sha256sum ./*.mp4 | sed 's| \./| |' > SHA256SUMS
cat SHA256SUMS
echo "Inputs ready. Checksums written to data/inputs/SHA256SUMS (commit it)."
