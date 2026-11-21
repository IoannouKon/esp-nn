#!/usr/bin/env bash
set -euo pipefail
kit=$(cd "$(dirname "$0")/.." && pwd)
workspace=$(cd "$1" && pwd)
group=$2
shift 2
for version in stock opt2 mean combined; do
    app="$workspace/$version/app"
    python3 "$kit/scripts/stage_suite.py" "$app" "$@"
    (cd "$app" && idf.py --ccache -DIDF_TARGET=esp32s3 -DCNN_DIAGNOSTIC=OFF "-DCNN_ARENA_BYTES=${CNN_ARENA_BYTES:-2097152}" reconfigure && ninja -C build -j4) \
        >"$kit/results/build/$group-$version-build.log" 2>&1
    python3 "$kit/scripts/save_build_evidence.py" "$workspace" "$version" "$group"
done
