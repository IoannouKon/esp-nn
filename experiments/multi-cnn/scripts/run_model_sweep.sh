#!/usr/bin/env bash
# Build/flash/capture a SINGLE frozen CNN across four isolated worktrees.
# Prerequisites: IDF exported, dependencies installed as documented, serial port free.
set -euo pipefail
KIT="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACES="${1:?Path to 4-worktree workspace}"
MODEL="${2:?model name under kit/models}"
PORT="${3:-/dev/ttyACM0}"
M="$KIT/models/$MODEL"
[[ -s "$M/model.tflite" && -s "$M/input.bin" ]] || { echo "Missing frozen model/input: $M";exit 2; }
OUT="$KIT/results/logs/$MODEL";mkdir -p "$OUT"
# Interleave builds across versions. Two boots per version.
ORDER=(stock opt2 mean combined combined mean opt2 stock)
for sequence in "${!ORDER[@]}"; do
    version="${ORDER[$sequence]}"
    boot=1
    [[ "$sequence" -ge 4 ]] && boot=2
    WORKTREE="$WORKSPACES/$version/esp-nn"
    APP="$WORKTREE/experiments/multi-cnn/app"
    [[ -f "$APP/main/main.cc" ]] || { echo "APP NOT INSTALLED: $APP"; exit 3; }
    [[ -d "$WORKTREE/experiments/multi-cnn/esp-tflite-micro" ]] || { echo "ESP-TFLM NOT INSTALLED: $WORKTREE";exit 4; }
    cp "$M/model.tflite" "$APP/main/model.tflite"
    cp "$M/input.bin" "$APP/main/input.bin"
    (
      cd "$APP"
      idf.py build > "$OUT/$version-$boot-build.log" 2>&1
      idf.py -p "$PORT" flash > "$OUT/$version-$boot-flash.log" 2>&1
    )
    sha256sum "$APP/main/model.tflite" "$APP/main/input.bin" >> "$OUT/artifacts.sha256"
    python3 "$KIT/scripts/capture_serial.py" --port "$PORT" --timeout 1200 \
        --out "$OUT/$version-$boot.log"
    grep -a 'CNN_DONE' "$OUT/$version-$boot.log" | tail -1
    echo "RECORDED $MODEL $version boot=$boot"
done
python3 "$KIT/scripts/compare_cnn.py" "$KIT/results/logs" --out "$KIT/results/analysis/comparison"
