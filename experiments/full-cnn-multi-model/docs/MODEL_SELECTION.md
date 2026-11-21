# Benchmark model selection and rationale

## Tier 1: public pretrained INT8 CNN reference models

| ID | Network / task | Source | Input (reported upstream) | Approx model size | Priority | Target kernel interpretation |
|---|---|---|---|---:|---|---|
| `mlperf_cifar10_resnet8` | MLPerf Tiny CIFAR-10, 3-block ResNet8 classifier | `mlcommons/tiny` pinned commit | 32×32×3 INT8 | 512 KB | Mandatory | Different realistic convolutional CNN; MaxPool/MEAN may be absent. |
| `mlperf_vww_mobilenet` | MLPerf Tiny visual wake words, MobileNetV1 | `mlcommons/tiny` | 96×96×3 INT8 | 333 KB | Mandatory | Depthwise + pointwise CNN; test compatibility and actual operators. |
| `tflm_person_detection` | Official TFLM person detector, MobileNetV1 0.25, grayscale | `tensorflow/tflite-micro` | 96×96×1 INT8 | 301 KB | Mandatory | Full CNN control and ESP-specific pretrained example. |
| `mlperf_kws_dscnn` | MLPerf Tiny keyword spotting, DS-CNN | `mlcommons/tiny` | 49×10×1 INT8 | 54 KB | Mandatory | Audio-feature CNN, not an image classifier. |
| `mlperf_cifar10_resnet6` | MLPerf Tiny larger 6-block ResNet | `mlcommons/tiny` | 32×32×3 INT8 | 797 KB | Optional | Scaling stress test; verify memory and supported ops. |
| `mlperf_vww_14block` | MLPerf Tiny larger VWW MobileNet | `mlcommons/tiny` | 96×96×3 INT8 | 989 KB | Optional | Scaling stress test; may exceed practical memory. |
| `mlperf_vww_20block` | MLPerf Tiny larger VWW MobileNet | `mlcommons/tiny` | 96×96×3 INT8 | 966 KB | Optional | Another independent depth variant. |

The exact asset URLs and pinned upstream commits are in `PRETRAINED_MODELS.json`. For three reference models published upstream model hashes are recorded and verified by the downloader. The others are fetched from a pinned commit and their actual hashes frozen in generated metadata; no unverified hash is described as a published checksum.

## Tier 2: controlled CNNs that definitely contain target operators at graph design time

- `mnist_fixed`: **already benchmarked** on this exact board, 28×28 grayscale input, `Conv2D → MaxPool(3×3 SAME/stride1) → Conv2D → MaxPool(5×5 SAME/stride1) → Dense`. Historical full inference: 2.910 ms stock vs 2.660 ms Opt2, exact outputs, +8.59% lower latency. Board artifact is fetched via `scripts/prepare_mnist.sh` from your Git branch.
- `max3`, `max5`: custom CIFAR10 CNNs trained from scratch, eligible MaxPool layout intended, no MEAN.
- `mean_only`: custom CIFAR10 CNN containing `GlobalAveragePooling2D` → TFLite `MEAN` (verify conversion). Needs validated MEAN-to-ESP-NN adapter to exercise QACC.
- `both`, `depthwise_both`: custom CIFAR10 CNNs containing both types in the graph (subject to converter op lowering).
- `avg_control`, `neutral_control`: negative controls.

Custom models are trained using `scripts/generate_models.py`. **They are not official pretrained reference models.** Training accuracy in metadata is evidence of training only, not the goal of this latency benchmark. Avoid calling 1–2-epoch models production quality.

## Required validation before a performance claim

1. Model bytes present, source commit and SHA256 stored. No shape changes to fit RAM.
2. `scripts/inspect_models.py` shows actual INT8 I/O, full operator list, shape, host output and eligible paths.
3. ESP-IDF compile succeeds with pinned ESP-TFLM and the selected local ESP-NN branch; `check_build_sources.py` verifies the compiled source paths.
4. ESP-TFLM interpreter returns OK and full INT8 output matches exactly across builds, each and every run.
5. 30 timings per boot, 2 boots per build. Report both cycles and µs, memory, source commits, all SKIPs and regressions.
6. Instrument candidate optimized code in a separate **untimed** diagnostic invocation to confirm actual MaxPool or MEAN dispatch. No instrumentation in final timed binaries.
7. Stop and mark `INCONCLUSIVE` for EXP-MEAN if the TFLM→ESP-NN mean bridge does not exist or does not reproduce baseline outputs bit-for-bit.

This is a **controlled inference latency** experiment, not an official MLPerf Tiny submission. The fixed random input does not replace the required MLPerf accuracy dataset/conditions.
