# Model matrix and truth-in-advertising

## Repeatable models in this kit

| Name | Origin | Optimized operators expected | Artifact status |
|---|---|---|---|
| mnist_fixed | Previously trained INT8 MNIST CNN, frozen 25 KB file | Opt2 max 3x3 and 5x5 | Exact bytes fetched from user's Git revision by prepare_mnist.sh |
| max3 | Custom trained CIFAR-10 CNN | Opt2 3x3 | Generated via generate_models.py |
| max5 | Custom trained CIFAR-10 CNN | Opt2 5x5 | Generated via generate_models.py |
| mean_only | Custom trained CIFAR-10 CNN | TFLM MEAN, NOT ESP-NN by default | Generated |
| both | Custom trained CIFAR-10 CNN | Opt2 max, TFLM MEAN reference | Generated |
| depthwise_both | Custom trained CIFAR-10 CNN, depthwise convolutions | Opt2 max, TFLM MEAN reference | Generated |
| avg_control | Custom trained CIFAR-10 CNN | Negative control: average pool | Generated |
| neutral_control | Custom trained CIFAR-10 CNN | Negative control: neither | Generated |

All 7 CIFAR variants are custom architectures, NOT MobileNet/EfficientNet, and the default 1-epoch training is for executing real inference, not competitive model accuracy. Their ability to allocate in ESP32-S3 cannot be certified without executing the board; the agent must record build, `AllocateTensors`, and Invoke status per case.

## External architecture track, CONDITIONAL (do not fake these)

1. **Person Detection**: Available from Espressif ESP-TFLite Micro example; can attempt to extract `g_person_detect_model_data` into `.tflite`, freeze its known input. Expect max and mean not to execute, based on prior experiment.
2. **MobileNetV2 INT8**: Acquire publicly licensed pretrained TFLite with downloadable model, reproducible source, input preprocessing, model digest. TFLM supported operator subset and arena footprint are blockers; run only if validated.
3. **MobileNetV3-Small INT8**: Same; includes squeeze-and-excite and often MEAN. Must verify TFLM's MEAN dispatch; without adapter EXP-MEAN does not run.
4. **EfficientNet-Lite0 INT8**: Public TensorFlow model, but ESP32-S3-EYE memory and TFLM supported ops might prevent execution. Do NOT replace with EfficientNetB0 or pretend it is Lite0. If unavailable, label SKIPPED(reason), with evidence.

Optional external candidates are *not bundled binaries*. Do not claim they are already supported or run. There are 8 reproducible model *recipes* and 4 conditional real-world architectures.

## Critical MEAN routing caveat

Source `espressif/esp-tflite-micro/tensorflow/lite/micro/kernels/reduce.cc` registers `Register_MEAN` to `EvalMeanHelper` in `reduce_common.cc` which uses TFLM reference `QuantizedMeanOrSumExtraArgs`. It DOES NOT call `esp_nn_mean_nhwc_s8`.

Thus a naive four-firmware comparison tests **Opt2 only**. The EXP-MEAN and combined firmware have identical TFLM MEAN execution unless a separate, correct, explicitly documented integration is added. The agent must implement and validate a real ESP-NN MEAN dispatch adapter or must return `EXP-MEAN-CNN-INCONCLUSIVE` rather than a fabricated result.

For integration: only attempt 4D NHWC INT8 global reductions across axes [1,2] with supported quantization and shape. Verify the precise TFLM-to-ESP-NN scale/multiplier/zero-point mapping against TFLM reference output, including zeros, extremes, random inputs, nontrivial scales, and all model tensors; use old EvalMean for all unsupported cases. Validate before timed runs and remove debug/reference checking from timing. If outputs differ, this optimization is not applicable to that graph with those parameters—do not alter weights, outputs or rounding to force a pass. Measure integration overhead and attribute it separately.

## Attribution

- Opt2 branch also includes Opt1's 128-bit SIMD optimization. Label its result as **Opt1+Opt2 versus stock**. For specific model max 3x3/5x5 stride1 SAME paths, prove sliding selection.
- Keep experimental kernel branches unchanged; only create detached A/B/C/D worktrees. Build `combined` as an uncommitted isolated working tree and save exact production diff SHA.
- Full-model inference is not official Espressif published CNN benchmark. Distinguish trained-MNIST precedent, custom CIFAR models, and verified external pretrained models.
