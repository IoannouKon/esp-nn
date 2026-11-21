#!/usr/bin/env bash
# Reuse the original monitor and four-variant timed runner in isolated result directories.
set -euo pipefail
ext=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
kit=$(dirname "$ext")
workspace=$(realpath "${1:?Usage: run_study.sh WORKSPACE [PORT] [all|correctness|full|profile] [MODEL ...]}")
port=${2:-/dev/ttyACM0}
phase=${3:-all}
shift "$(( $# < 3 ? $# : 3 ))"
models=("$@")
if [[ ${#models[@]} = 0 ]]; then
    models=(cifar_mean_wide cifar_mean_large mean_only both depthwise_both)
fi

variants=(stock opt2 mean combined)
pins=(ace42ac7721119cd543fc40ffe719e601fa8f20f edb003c6770491abb74766835f4c803b9d4f5a20 4bfa49c64a932f700688c2007a01d8ea1fa102ac 4bfa49c64a932f700688c2007a01d8ea1fa102ac)
tflm=df8722334a80ceabc609c1e72968f417cd9437f1
diff_paths=(src/pooling/esp_nn_max_pool_s8_esp32s3.S src/pooling/esp_nn_max_pool_s8_esp32s3.c)
for i in "${!variants[@]}"; do
    variant=${variants[i]}
    nn="$workspace/$variant/esp-nn"
    micro="$workspace/$variant/esp-tflite-micro"
    [[ $(git -C "$nn" rev-parse HEAD) == "${pins[i]}" ]]
    [[ $(git -C "$micro" rev-parse HEAD) == "$tflm" ]]
    [[ -z $(git -C "$micro" status --porcelain --untracked-files=no -- . ':(exclude)idf_component.yml') ]]
    [[ $(git -C "$micro" diff --numstat -- idf_component.yml | awk '{print $1,$2}') == "1 0" ]]
    if [[ "$variant" = combined ]]; then
        cmp <(git -C "$nn" diff --binary --no-color HEAD -- "${diff_paths[@]}") \
            <(git -C "$nn" diff --binary --no-color "${pins[0]}" "${pins[1]}" -- "${diff_paths[@]}")
        [[ -z $(git -C "$nn" status --porcelain --untracked-files=no -- . "${diff_paths[@]/#/:(exclude)}") ]]
    else
        [[ -z $(git -C "$nn" status --porcelain --untracked-files=no) ]]
    fi
done
if [[ $(idf.py --version) != 'ESP-IDF v5.5.1'* ||
      $(git -C "${IDF_PATH:?Source ESP-IDF export.sh first}" rev-parse HEAD) != fcae32885b0296b32044cb99ecbdc50d98dddb83 ]]; then
    echo 'Expected ESP-IDF v5.5.1 environment' >&2
    exit 1
fi

staging=$(mktemp -d -t espnn-global-mean-study.XXXXXXXX)
trap 'rm -rf -- "$staging"' EXIT
mkdir -p "$staging/models" "$staging/results" "$ext/results"/{full,profile,diagnostics,analysis}
cp -a "$kit/scripts" "$kit/integration" "$staging/"
for model in "${models[@]}"; do
    source="$kit/models/$model"
    if [[ -e "$ext/models/$model/model.tflite" ]]; then
        source="$ext/models/$model"
    fi
    ln -s "$source" "$staging/models/$model"
    [[ -s "$source/model.tflite" && -s "$source/input.bin" && -s "$ext/models/$model/correctness_inputs.bin" ]]
done
ln -s "$ext/results/diagnostics" "$staging/results/diagnostics"
cp "$kit/results/diagnostics/mean-bridge-qualified.txt" "$ext/results/diagnostics/mean-bridge-qualified.txt"
export CNN_WATCHDOG_MS=0 CNN_ARENA_BYTES=2097152
provenance() {
    local out=$1
    local variant=$2
    local app="$workspace/$variant/app"
    sha256sum "$app/main/"{main.cc,mean_bridge.cc,mean_bridge.h,model.tflite,input.bin} > "$out/$variant-staged-source.sha256"
    cp "$app/sdkconfig" "$out/$variant-probe.sdkconfig"
    cp "$app/dependencies.lock" "$out/$variant-probe.dependencies.lock"
    sha256sum "$app/build/espnn_multi_cnn.elf" > "$out/$variant-probe.elf.sha256"
    sha256sum "$app/main/correctness_inputs.bin" > "$out/$variant-probe-inputs.sha256"
    python3 - "$app/build/espnn_multi_cnn.bin" "$app/main" <<'PY'
from pathlib import Path
import sys
binary = Path(sys.argv[1]).read_bytes()
source = Path(sys.argv[2])
assert all((source / name).read_bytes() in binary for name in ('model.tflite', 'input.bin', 'correctness_inputs.bin'))
PY
}
correctness() {
    local model=$1
    local out="$ext/results/diagnostics/$model"
    mkdir -p "$out"
    python3 "$ext/scripts/stage_app.py" "$workspace" correctness --cases "$ext/models/$model/correctness_inputs.bin"
    for variant in "${variants[@]}"; do
        if [[ -e "$out/$variant-probe.log" ]]; then
            echo "Refusing to overwrite $out/$variant-probe.log" >&2
            exit 2
        fi
        echo "CORRECTNESS $model $variant"
        # Clear the watchdog cache left by the original ResNet6 trial.
        (cd "$workspace/$variant/app" && idf.py --ccache -DCNN_WATCHDOG_MS=0 -DCNN_DISPATCH_PROBE=ON reconfigure) \
            > "$out/$variant-configure.log" 2>&1
        bash "$staging/integration/run_diagnostic.sh" "$workspace" "$model" "$variant" probe "$port"
        provenance "$out" "$variant"
    done
}
timed() {
    local mode=$1
    local model=$2
    local out="$ext/results/$mode"
    if [[ -d "$out/$model" && -n $(ls -A "$out/$model") ]]; then
        echo "Refusing to overwrite $out/$model" >&2
        exit 2
    fi
    ln -sfn "$out" "$staging/results/logs"
    echo "TIMING $mode $model"
    python3 "$ext/scripts/stage_app.py" "$workspace" "$mode"
    bash "$staging/scripts/run_one_model.sh" "$workspace" "$model" "$port"
    for variant in "${variants[@]}"; do
        sha256sum "$workspace/$variant/app/main/"{main.cc,mean_bridge.cc,mean_bridge.h,model.tflite,input.bin} \
            > "$out/$model/$variant-staged-source.sha256"
    done
}

case "$phase" in
    all)
        for model in "${models[@]}"; do
            correctness "$model"
            if [[ "$model" = cifar_mean_wide || "$model" = cifar_mean_large ]]; then
                timed full "$model"
            fi
        done
        for model in "${models[@]}"; do timed profile "$model"; done
        ;;
    correctness) for model in "${models[@]}"; do correctness "$model"; done ;;
    full|profile) for model in "${models[@]}"; do timed "$phase" "$model"; done ;;
    *) echo "Unknown phase $phase" >&2; exit 3 ;;
esac
