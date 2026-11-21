#!/usr/bin/env bash
set -euo pipefail
base=$(cd "$(dirname "$0")" && pwd)
cd "$base/cnn_opt2"
source ~/esp_s3/esp-idf/export.sh >"$base/results/idf-env.log" 2>&1
git -C "$IDF_PATH" rev-parse HEAD >"$base/results/idf-git.txt"
git -C "$IDF_PATH" status --short >>"$base/results/idf-git.txt"
xtensa-esp32s3-elf-gcc --version >"$base/results/compiler.txt"
idf.py --version >>"$base/results/compiler.txt"
build_run() {
    local label=$1 rev=$2 probe=$3 boots=$4
    git -C "$base/espressif__esp-nn" checkout --detach "$rev"
    git -C "$base/espressif__esp-nn" rev-parse HEAD >"$base/results/$label.esp-nn.txt"
    idf.py --ccache -B build-cnn -DIDF_TARGET=esp32s3 -DPROBE_OPT2="$probe" build >"$base/results/$label.build.log" 2>&1
    cmp sdkconfig "$base/results/original.sdkconfig"
    cp sdkconfig "$base/results/$label.sdkconfig"
    cp dependencies.lock "$base/results/$label.dependencies.lock"
    cp build-cnn/project_description.json "$base/results/$label.project.json"
    cp build-cnn/compile_commands.json "$base/results/$label.compile_commands.json"
    elf=$(find build-cnn -maxdepth 1 -name '*.elf' -print -quit)
    sha256sum "$elf" >"$base/results/$label.elf.sha256"
    xtensa-esp32s3-elf-nm -S -C "$elf" | awk '/esp_nn_max_pool|esp_nn_mean|Register_MEAN|Register_MAX_POOL/ {print}' >"$base/results/$label.symbols.txt"
    /usr/bin/python3 "$base/capture.py" "$base/results/$label.log" "$boots"
    printf 'Finished %s\n' "$label"
}
build_run stock ace42ac7721119cd543fc40ffe719e601fa8f20f OFF 2
build_run opt2-probe edb003c6770491abb74766835f4c803b9d4f5a20 ON 1
build_run opt2 edb003c6770491abb74766835f4c803b9d4f5a20 OFF 2
build_run exp-mean 4bfa49c64a932f700688c2007a01d8ea1fa102ac OFF 2
