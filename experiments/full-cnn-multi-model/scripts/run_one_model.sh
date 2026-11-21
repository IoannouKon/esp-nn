#!/usr/bin/env bash
# Run one frozen model across Stock/Opt2/Mean/Combined, with 2 independent resets each.
set -euo pipefail
KIT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SPACE="${1:?Usage: run_one_model.sh /workspace model_name [port]}"
MODEL="${2:?Model name under kit/models/}"
PORT="${3:-/dev/ttyACM0}"
DATA="$KIT/models/$MODEL"
[[ -s "$DATA/model.tflite" && -s "$DATA/input.bin" ]] || { echo "Missing model/input: $DATA" >&2;exit 2; }
SPACE="$(cd "$SPACE" && pwd)"
OUT="$KIT/results/logs/$MODEL";mkdir -p "$OUT"
printf '%s  %s\n' "$(sha256sum "$DATA/model.tflite"|cut -d' ' -f1)" model.tflite "$(sha256sum "$DATA/input.bin"|cut -d' ' -f1)" input.bin > "$OUT/model-input.sha256"
for pair in stock:1 opt2:1 mean:1 combined:1 combined:2 mean:2 opt2:2 stock:2; do
    variant=${pair%%:*};boot=${pair##*:};APP="$SPACE/$variant/app"
    [[ -f "$APP/main/main.cc" ]] || { echo "Missing prepared app: $APP" >&2;exit 3; }
    cmp -s "$DATA/model.tflite" "$APP/main/model.tflite" || cp "$DATA/model.tflite" "$APP/main/model.tflite"
    cmp -s "$DATA/input.bin" "$APP/main/input.bin" || cp "$DATA/input.bin" "$APP/main/input.bin"
    (
      cd "$APP"
      if [[ ! -f sdkconfig ]]; then
          idf.py --ccache set-target esp32s3 > "$OUT/$variant-set-target.log" 2>&1
      fi
      idf.py --ccache -DCNN_DISPATCH_PROBE=OFF -DCNN_MEAN_STRESS_ONLY=OFF "-DCNN_WATCHDOG_MS=${CNN_WATCHDOG_MS:-0}" "-DCNN_ARENA_BYTES=${CNN_ARENA_BYTES:-2097152}" build > "$OUT/$variant-$boot-build.log" 2>&1
    )
    python3 "$KIT/scripts/check_build_sources.py" "$APP/build" "$SPACE/$variant/esp-nn" "$SPACE/$variant/esp-tflite-micro" > "$OUT/$variant-$boot-source-check.txt"
    if [[ "$boot" = 1 ]]; then
      python3 - "$APP/build/compile_commands.json" "$OUT/$variant-compile-selected.json" <<'PYC'
import json,re,sys
from pathlib import Path
compiled=json.loads(Path(sys.argv[1]).read_text())
selected=[x for x in compiled if re.search(
    r'/main/(?:main|mean_bridge)\.cc$|/esp-nn/src/(?:pooling|common)/esp_nn_(?:max_pool|mean)|/kernels/esp_nn/(?:pooling|reduce)\.cc$',x['file'])]
assert selected
Path(sys.argv[2]).write_text(json.dumps(selected,indent=2)+'\n')
PYC
    fi
    cp "$APP/sdkconfig" "$OUT/$variant-$boot.sdkconfig"
    cmp "$OUT/stock-1.sdkconfig" "$OUT/$variant-$boot.sdkconfig"
    cp "$APP/dependencies.lock" "$OUT/$variant-$boot.dependencies.lock"
    elf=$(find "$APP/build" -maxdepth 1 -name '*.elf' -print -quit)
    sha256sum "$elf" >"$OUT/$variant-$boot.elf.sha256"
    xtensa-esp32s3-elf-nm -S "$elf" | awk '/sliding_row_asm|mean_s8_16ch_qacc|mean_nhwc_s8|__wrap_esp_nn_/ {print}' >"$OUT/$variant-$boot.symbols.txt"
    if grep -q '__wrap_esp_nn_' "$OUT/$variant-$boot.symbols.txt"; then echo 'Timed firmware has diagnostic wrappers' >&2; exit 4; fi
    python3 - "$APP/build/${elf##*/}" "$DATA" <<'PYB'
from pathlib import Path
import sys
elf=Path(sys.argv[1])
binary=elf.with_suffix('.bin').read_bytes()
base=Path(sys.argv[2])
assert all((base/name).read_bytes() in binary for name in ('model.tflite','input.bin'))
PYB
    (cd "$APP" && idf.py --ccache -p "$PORT" flash) >"$OUT/$variant-$boot-flash.log" 2>&1
    python3 "$KIT/scripts/capture_idf_monitor.py" --app "$APP" --port "$PORT" --out "$OUT/$variant-$boot.log" --timeout 1200
    echo "OK: model=$MODEL variant=$variant boot=$boot"
done
python3 "$KIT/scripts/compare_cnn.py" "$KIT/results/logs" --out "$KIT/results/analysis/compare"
