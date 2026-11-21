#!/usr/bin/env bash
set -euo pipefail
src=$(cd "$1" && pwd)
workspace=$(cd "$2" && pwd)
tflm=df8722334a80ceabc609c1e72968f417cd9437f1
for version in stock opt2 mean combined; do
    base="$workspace/$version"
    test -f "$base/esp-nn/.git"
    mkdir "$base/esp-tflite-micro"
    git -C "$src" archive "$tflm" | tar -x -C "$base/esp-tflite-micro"
    ln -s esp-nn "$base/espressif__esp-nn"
    sed -i '/^    version: ">=1.4.2"/a\    override_path: "../espressif__esp-nn"' "$base/esp-tflite-micro/idf_component.yml"
done
