#!/usr/bin/env bash
# Download the MobileNet-SSD (Caffe, PASCAL VOC) detector into pipeline/models/ and verify checksums.
# Source: github.com/chuanqi305/MobileNet-SSD. The files are not stored in git.
set -euo pipefail

DIR="$(cd "$(dirname "$0")/.." && pwd)/pipeline/models"
BASE=https://raw.githubusercontent.com/chuanqi305/MobileNet-SSD/master
mkdir -p "$DIR"
cd "$DIR"

fetch() { [[ -f "$1" ]] || curl -fL --retry 3 -o "$1" "$BASE/$1"; }
fetch deploy.prototxt
fetch mobilenet_iter_73000.caffemodel

sha256sum -c - <<'EOF'
2d180f723b3109e21f8287f6b3c691390d07b60eed998327cd3259ffa0e50608  deploy.prototxt
52eed8be80522c152a17fb56740de705b79881bde1a167e0e747310523685fc7  mobilenet_iter_73000.caffemodel
EOF
echo "Model ready in $DIR"
