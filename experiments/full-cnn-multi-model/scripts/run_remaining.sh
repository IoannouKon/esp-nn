#!/usr/bin/env bash
# Continue with the frozen MNIST control, custom CNNs and optional pinned models.
set -uo pipefail
kit=$(cd "$(dirname "$0")/.." && pwd)
space=$(cd "$1" && pwd)
port=${2:-/dev/ttyACM0}
tflm_python=${TFLM_PYTHON:-python3}
cd "$kit"
run_model() {
    local model=$1
    echo "START $model"
    if bash scripts/run_one_model.sh "$space" "$model" "$port"; then
        printf '%s COMPLETE\n' "$model" | tee -a results/run-status.txt
    else
        printf '%s FAILED\n' "$model" | tee -a results/run-status.txt
    fi
}
train() {
    TF_CPP_MIN_LOG_LEVEL=3 TF_NUM_INTRAOP_THREADS=3 TF_NUM_INTEROP_THREADS=1 TF_ENABLE_ONEDNN_OPTS=0 TF_DETERMINISTIC_OPS=1 \
      "$tflm_python" -u - <<'PY'
import os
import runpy
import sys
from functools import partial
from keras.src.datasets import cifar10
if 'CNN_CIFAR_CACHE' in os.environ:
    cifar10.get_file = partial(cifar10.get_file, cache_dir=os.environ['CNN_CIFAR_CACHE'])
sys.argv=['scripts/generate_models.py','--epochs','2','--train-samples','20000','--only',
          'max3','max5','mean_only','both','depthwise_both']
runpy.run_path(sys.argv[0],run_name='__main__')
PY
}
train >results/cifar-training.log 2>&1 &
trainer=$!
bash integration/run_diagnostic.sh "$space" mnist_fixed combined probe "$port" || echo 'MNIST dispatch check failed'
run_model mnist_fixed
if wait "$trainer"; then
    TF_CPP_MIN_LOG_LEVEL=3 "$tflm_python" scripts/inspect_models.py >results/host-preflight-final.log 2>&1
    for variant in stock opt2 mean combined; do
       python3 integration/enable_bridge.py "$space/$variant/app" || exit 5
    done
    if bash integration/run_diagnostic.sh "$space" mnist_fixed stock stress "$port" &&
       bash integration/run_diagnostic.sh "$space" mnist_fixed combined stress "$port" &&
       grep -q 'MEAN_STRESS_DONE .*mismatches=0' results/diagnostics/mnist_fixed/stock-stress.log &&
       grep -q 'MEAN_STRESS_DONE .*mismatches=0' results/diagnostics/mnist_fixed/combined-stress.log; then
        mkdir -p results/diagnostics
        grep -h 'MEAN_STRESS_DONE' results/diagnostics/mnist_fixed/{stock,combined}-stress.log >results/diagnostics/mean-bridge-qualified.txt
    else
        echo 'MEAN BRIDGE UNQUALIFIED; reverting before timing the custom graphs'
        for variant in stock opt2 mean combined; do
            cp app/main/{main.cc,CMakeLists.txt} "$space/$variant/app/main/"
        done
    fi
    for model in max3 max5 mean_only both depthwise_both; do
        bash integration/run_diagnostic.sh "$space" "$model" combined probe "$port" || echo "Dispatch check failed: $model"
        run_model "$model"
    done
    for variant in stock opt2 mean combined; do
        cp app/main/{main.cc,CMakeLists.txt} "$space/$variant/app/main/"
    done
else
    echo 'Custom training failed; see results/cifar-training.log'
fi
bash scripts/run_optional.sh "$space" "$port"
