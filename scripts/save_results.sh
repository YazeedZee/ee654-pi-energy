#!/usr/bin/env bash
# Commit and push everything under data/raw/ (and docs/). Run on the Pi at the end of every session.
# Usage: ./scripts/save_results.sh ["optional message"]
set -euo pipefail

cd "$(dirname "$0")/.."
git add data/raw docs
if git diff --cached --quiet; then
  echo "Nothing new to save."
  exit 0
fi

NEW=$(git diff --cached --name-only data/raw | cut -d/ -f3 | sort -u | paste -sd, -)
MSG="${1:-results: ${NEW:-docs} ($(hostname), $(date +%Y-%m-%dT%H:%M))}"
git commit -q -m "$MSG"
git push -q && echo "Saved and pushed: $MSG" \
  || echo "Committed locally but push FAILED. Check the network, then run: git push"
