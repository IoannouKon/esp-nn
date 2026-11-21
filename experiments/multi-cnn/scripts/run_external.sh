#!/usr/bin/env bash
set -euo pipefail
kit=$(cd "$(dirname "$0")/.." && pwd)
workspace=$(cd "$1" && pwd)
group=$2
shift 2
app="$workspace/combined/app"
out="$kit/results/logs/suite_$group"
python "$kit/scripts/stage_suite.py" "$app" "$@"
for arena in 2097152 4194304 6291456; do
    if [ "$arena" -lt "${INITIAL_ARENA:-2097152}" ]; then continue; fi
    (cd "$app" && idf.py --ccache -B build-probe -DCNN_DIAGNOSTIC=ON "-DCNN_ARENA_BYTES=$arena" reconfigure &&
        ninja -C build-probe -j4) >"$kit/results/build/$group-combined-probe-$arena.log" 2>&1
    /usr/bin/python3 "$kit/scripts/run_suite.py" "$app" build-probe "$out/combined-diagnostic-$arena.log"
    if ! grep -Eq 'Failed to allocate (tail|temp|arena)|Failed to resize buffer|Arena size is too small|arena.*too small|buffer allocation failed' \
        "$out/combined-diagnostic-$arena.log"; then
        break
    fi
done
cp "$out/combined-diagnostic-$arena.log" "$out/combined-diagnostic.log"
cp "$out/combined-diagnostic-$arena.flash.log" "$out/combined-diagnostic.flash.log"
python "$kit/scripts/save_build_evidence.py" "$workspace" combined "$group" --build build-probe
CNN_ARENA_BYTES=$arena "$kit/scripts/build_matrix.sh" "$workspace" "$group" "$@"
"$kit/scripts/run_matrix.sh" "$workspace" "$group"
