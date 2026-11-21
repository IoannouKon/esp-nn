# Read before execution

## Already validated in this conversation / previous repository work

- Frozen MNIST classifier previously ran on the ESP32-S3-EYE with stock and Opt2 (the prior experiment reported 2.910 ms vs 2.660 ms). It still must be re-run by this agent in the present four-version environment.
- Original ESP-NN v1.5.0 and Opt2/EXP-MEAN production revisions are known. No user branch changes are needed.
- Source check: Espressif ESP-TFLite Micro `esp_nn/pooling.cc` calls ESP-NN max-pool in its INT8 path, but `reduce.cc`/`reduce_common.cc` implements INT8 MEAN as TFLM reference reduction.

## Validated locally in this ZIP

- Python files compile syntactically.
- `tests/smoke.py` validates that the result analyzer accepts completed, equivalent output logs and rejects incomplete logs.

## Explicitly NOT validated

- CIFAR models have not been trained or generated in this environment. They are deterministic generation recipes requiring TensorFlow and dataset access.
- The ESP-IDF app and Xtensa executable have not been compiled or flashed from this ZIP.
- External MobileNetV2/V3-Small, EfficientNet-Lite0 and Person Detection `.tflite` files are not included or proven to work in the generic runner.
- TFLM MEAN-to-ESP-NN adapter is not supplied as working code because its integer quantization equivalence has not been established. The agent is explicitly required to implement and validate it before making CNN-level EXP-MEAN performance claims.
- No new board-level CNN latency, correctness or memory numbers have been measured here.

This prevents an experimentally invalid claim of MEAN acceleration when only TFLM's reference MEAN actually ran.
