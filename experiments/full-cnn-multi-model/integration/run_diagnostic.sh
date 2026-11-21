#!/usr/bin/env bash
set -euo pipefail
kit=$(cd "$(dirname "$0")/.." && pwd)
workspace=$(cd "$1" && pwd)
model=$2
variant=$3
mode=$4
port=${5:-/dev/ttyACM0}
app="$workspace/$variant/app"
out="$kit/results/diagnostics/$model"
mkdir -p "$out"
data="$kit/models/$model"
for f in model.tflite input.bin; do
    cmp -s "$data/$f" "$app/main/$f" || cp "$data/$f" "$app/main/$f"
done
probe=OFF; stress=OFF
if [ "$mode" = stress ]; then stress=ON; else probe=ON; fi
(cd "$app" && idf.py --ccache -DCNN_DISPATCH_PROBE="$probe" -DCNN_MEAN_STRESS_ONLY="$stress" \
        "-DCNN_ARENA_BYTES=${CNN_ARENA_BYTES:-2097152}" build) >"$out/$variant-$mode-build.log" 2>&1
python3 "$kit/scripts/check_build_sources.py" "$app/build" "$workspace/$variant/esp-nn" \
    "$workspace/$variant/esp-tflite-micro" >"$out/$variant-$mode-source-check.txt"
(cd "$app" && idf.py --ccache -p "$port" flash) >"$out/$variant-$mode-flash.log" 2>&1
python3 "$kit/scripts/capture_idf_monitor.py" --app "$app" --port "$port" \
  --probe --out "$out/$variant-$mode.log" --timeout 1200
