#!/usr/bin/env bash
set -uo pipefail
kit=$(cd "$(dirname "$0")/.." && pwd)
space=$(cd "$1" && pwd)
port=${2:-/dev/ttyACM0}
cd "$kit"
for v in stock opt2 mean combined; do
    cp app/main/{main.cc,CMakeLists.txt} "$space/$v/app/main/" || exit 2
done
for model in mlperf_vww_14block mlperf_vww_20block mlperf_cifar10_resnet6; do
    timeout=0
    if [[ "$model" = mlperf_cifar10_resnet6 ]]; then timeout=20000; fi
    echo "START $model"
    if CNN_WATCHDOG_MS=$timeout bash scripts/run_one_model.sh "$space" "$model" "$port"; then
        printf '%s COMPLETE\n' "$model" | tee -a results/run-status.txt
    else
        printf '%s FAILED\n' "$model" | tee -a results/run-status.txt
    fi
done
python3 scripts/compare_cnn.py results/logs --out results/analysis/compare
