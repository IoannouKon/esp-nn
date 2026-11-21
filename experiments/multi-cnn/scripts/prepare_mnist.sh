#!/usr/bin/env bash
set -euo pipefail
# Fetches THE SAME FROZEN model and input used in prior Opt2 proof of concept.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
REPO="${1:?Pass path to local IoannouKon/esp-nn Git clone or worktree}"
REV=edb003c6770491abb74766835f4c803b9d4f5a20
DST="$ROOT/models/mnist_fixed"; mkdir -p "$DST"
for file in model.tflite input.bin; do
  git -C "$REPO" show "$REV:experiments/full-cnn-opt2/cnn_opt2/main/$file" > "$DST/$file"
done
cp /dev/null "$DST/source.txt"
printf '%s\n' "Source: IoannouKon/esp-nn commit $REV; trained MNIST, frozen original model and input" > "$DST/source.txt"
sha256sum "$DST/model.tflite" "$DST/input.bin"
