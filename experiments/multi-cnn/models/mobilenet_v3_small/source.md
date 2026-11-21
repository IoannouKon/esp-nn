---
license: bsd-3-clause
pipeline_tag: image-classification
library_name: litert
base_model: torchvision/mobilenet_v3_small
base_model_relation: quantized
tags:
  - arm
  - arm-optimized
  - premium-smartphone
  - litert
---

# MobileNetV3-Small optimized for Arm-based mobile CPUs with SME2

An INT8-quantized version of mobilenet_v3_small for image classification, exported to LiteRT (`.tflite`) and optimized for Arm-based mobile CPUs with SME2.

## Summary

This repository contains an Arm-optimized version of mobilenet_v3_small for image classification, quantized to INT8 via static post-training quantization — per-channel symmetric weights, per-tensor affine activations. The model is provided in LiteRT (`.tflite`) format, targeting Mobile CPU systems.

This version is intended to demonstrate efficient inference on Arm-based platforms while preserving the original model's intended behavior. Arm evaluated the model on ImageNet-1k and measured the published performance and memory results on a representative evaluation target. The included Python example and locked uv environment target a Linux arm64 host; the representative evaluation target measurements must not be interpreted as Linux host performance results.

**Key results**

| Area | Result |
|---|---|
| Model format | LiteRT (`.tflite`) |
| Target device class | Mobile CPU |
| Reference device | vivo X300 (C1-Ultra, C1-Premium, C1-Pro, Android 16 / OriginOS 6) |
| Example environment | AWS Graviton, Ubuntu arm64 |
| Primary performance result | p50 latency 3.052 ms (1.91x faster than baseline), 322.84 frames per second |
| Accuracy result | Top-1 65.28%, Top-5 86.01% |
| Size / memory result | 2.816 MB (3.48x smaller), peak memory 27.87 MB (1.45x less) |

## Original model

| Field | Value |
|---|---|
| Original model | torchvision/mobilenet_v3_small |
| Original source | [torchvision/models/mobilenetv3.py](https://github.com/pytorch/vision/blob/main/torchvision/models/mobilenetv3.py) |
| Original developer | Google (torchvision implementation by PyTorch contributors) |
| Original model card | [torchvision.models.mobilenet_v3_small](https://docs.pytorch.org/vision/main/models/generated/torchvision.models.mobilenet_v3_small.html) |
| Original license | [BSD-3-Clause](https://github.com/pytorch/vision/blob/main/LICENSE) |

## Model files

| File | Description |
|---|---|
| `mobilenet_v3_small_android_litert_optimized.tflite` | Arm-optimized INT8 model for deployment |
| `example.py` | Minimal inference example |
| `pyproject.toml` | Pinned runtime dependencies for `example.py`, resolved with uv |
| `uv.lock` | Locked dependency resolution for `pyproject.toml` |
| `config.yaml` | Model I/O contract used by the example |
| `benchmarks/` | FP32 baseline and Arm-optimized benchmark records |

## Performance

Performance was measured on the reference configuration below. Results are intended to make the optimization reproducible but do not guarantee identical performance on every Arm-based system.

**Reference configuration**

| Field | Value |
|---|---|
| Device / platform | vivo X300 |
| CPU | C1-Ultra, C1-Premium, C1-Pro, 8 cores |
| System memory | 16 GB |
| OS | android, Android 16 / OriginOS 6 |
| Runtime | LiteRT 0.8.0 |
| Execution backend | CPU (XNNPACK, KleidiAI) |
| Precision | INT8, static PTQ — per-channel symmetric weights, per-tensor affine activations |
| Batch size | 1 |
| Input resolution | 224x224 |
| Runs / warmup | 50 / 10 |

**Performance results**

| Metric | Original / baseline | Arm-optimized | Improvement |
|---|---:|---:|---:|
| Model size (MB) | 9.81 | 2.816 | 3.48x smaller |
| End-to-end latency p50 (ms) | 5.82 | 3.052 | 1.91x faster |
| Peak memory (MB) | 40.46 | 27.87 | 1.45x less |
| Frames per second | 171.82 | 322.84 | 1.88x |

84.5% of the graph was delegated to XNNPACK.

## Accuracy

Accuracy was evaluated using the same preprocessing, input resolution, and evaluation protocol described below. Where possible, the optimized model is compared against the original model under the same evaluation conditions.

**Evaluation setup**

| Field | Value |
|---|---|
| Dataset | ImageNet-1k |
| Split | val |
| Sample count | 50000 |
| Metric(s) | Top-1 accuracy, Top-5 accuracy |
| Runtime | LiteRT 0.8.0 (CPU, XNNPACK, KleidiAI) |

**Accuracy results**

| Metric | Original / baseline | Arm-optimized | Change |
|---|---:|---:|---:|
| Top-1 accuracy (%) | 66.97 | 65.28 | -1.69 pp |
| Top-5 accuracy (%) | 87.13 | 86.01 | -1.12 pp |

Accuracy was measured using the evaluation setup described above. Users should re-evaluate the model on their own data before production use.

## Arm optimization approach

Arm optimized this model for efficient inference on Arm-based platforms using a hardware-aware conversion and validation flow.

For this release, Arm used:

| Optimization area | Applied? | Notes |
|---|---|---|
| Model conversion | Yes | Converted to LiteRT `.tflite` |
| Quantization | Yes | INT8 PTQ-static — per-channel symmetric weights, per-tensor affine activations; calibrated on 500 ImageNet-1k samples; selected layers were skipped from quantization to keep accuracy within acceptable ranges |
| Runtime/backend selection | Yes | LiteRT CPU with XNNPACK and KleidiAI |
| Graph/runtime compatibility updates | Yes | Performed as part of the LiteRT export pipeline |
| Accuracy validation | Yes | Compared against the original model or published baseline |
| Performance validation | Yes | Measured on the reference Arm platform |

The goal of this process is to improve deployment characteristics such as latency, memory use, model size, and runtime compatibility while preserving the model's intended behavior. Detailed conversion scripts, calibration configuration, or backend-specific implementation details may be provided separately where appropriate.

## Using this model

### Python environment

A representative evaluation target for this model is an Android handset, which does not run Python and uv. The environment recorded in `.python-version`, `pyproject.toml`, and `uv.lock` describes the AWS Graviton host the example was locked and run on. No Graviton latency or memory benchmark is reported here — the figures in the Performance section were measured on the vivo X300 itself.

The example was tested with Python 3.14.7 and `ai-edge-litert` 2.2.0 on Ubuntu 24.04 (glibc 2.39). It requires the runtime's XNNPACK CPU delegate, which LiteRT reports applying at interpreter construction. No native packages beyond the Python wheels are needed.

### Install dependencies

Dependencies are declared in `pyproject.toml`, which ships with this repository. Resolve and install them into a local virtual environment with uv:

```bash
uv python install
uv sync --frozen
```

### Run the example

```bash
uv run example.py
```

Note: The Python/uv example runs on AWS Graviton (Ubuntu arm64) to confirm runtime compatibility only, and is intended as a guideline for building an equivalent run script on Mobile CPU systems.

An ordinary run only prints the top-5 predictions and writes nothing. To also save them as JSON, pass an output path:

```bash
uv run example.py --output my_predictions.json
```

### Expected input

| Property | Value |
|---|---|
| Shape | [1, 3, 224, 224] |
| Dtype | float32 |
| Range | [0.0, 1.0] before normalization |
| Preprocessing | resize the shorter edge to 232 (bilinear), center crop to 224x224, to tensor, normalize (mean [0.485, 0.456, 0.406], std [0.229, 0.224, 0.225]) |

### Expected output

| Property | Value |
|---|---|
| Shape | [1, 1000] |
| Dtype | int8, quantized with scale 0.16559289395809174 and zero point -14 |
| Format | Per-class logits over 1000 ImageNet-1k classes |
| Postprocessing | dequantize `(int8_value - zero_point) * scale`, softmax, top-5 |

## Intended use

This model is intended for developers evaluating image classification workloads on Arm-based platforms. It is suitable as a reference implementation for benchmarking, prototyping, and integration exploration.

## Limitations

- Performance depends on the target device, runtime version, backend/delegate support, memory configuration, and system load.
- Accuracy was evaluated on the ImageNet-1k val split (50000 images) and may not generalize to all domains.
- INT8 quantization costs 1.69 pp Top-1 and 1.12 pp Top-5 against the FP32 baseline. For accuracy-critical use cases, evaluate the FP32 baseline before committing to the quantized variant.
- Fixed input size of 224x224 — the shortest edge is resized to 232 with the aspect ratio preserved, then the center 224x224 region is cropped, so content outside that crop is discarded.
- The model expects ImageNet-class inputs; out-of-distribution images still return a top-1 prediction with no abstention signal.
- This release preserves the original model's intended task and behavior, but users should validate it for their own application, data, and deployment environment.
- This repository is not a replacement for the original model documentation.

## Additional notes

Some layers were kept in FP32 and skipped from quantization to keep accuracy within acceptable ranges: the stem convolution and the first inverted-residual depthwise convolution, whose INT8 error propagates through the 50+ downstream convolutions, and every `hardsigmoid` op, for which XNNPACK has no quantized kernel. The classifier linear layer is kept out of Core ATen decomposition so it stays delegate-friendly.

- Sample input: `sample_input.jpg` is derived from [Samoyed on Beach](https://commons.wikimedia.org/wiki/File:Samoyed_on_Beach.jpg) by Appleinfl, via Wikimedia Commons (public domain).

## About this version

Original Model:
torchvision/mobilenet_v3_small by Google (torchvision implementation by PyTorch contributors) - [Repository](https://docs.pytorch.org/vision/main/models/generated/torchvision.models.mobilenet_v3_small.html)

Optimization/conversion:
Arm-Optimized version for execution on Arm-based platforms.

Converted/optimized by:
Arm

License:
The Original Model and the Optimized Model are subject to [BSD-3-Clause](https://huggingface.co/datasets/choosealicense/licenses/blob/main/markdown/bsd-3-clause.md).

This repository contains a converted or optimized version of the Original Model (the “Optimized Model”). The Original Model has been converted or optimized as described above for execution on Arm-based platforms.

No retraining or fine-tuning of the Original Model was performed as part of the conversion or optimization. The conversion or optimization was not intended to change the Original Model’s behavior or intended use.

### Original Model and Documentation

For information about the Original Model, including its development, training data, intended uses, limitations and other relevant information, please refer to the [Original Model repository](https://docs.pytorch.org/vision/main/models/generated/torchvision.models.mobilenet_v3_small.html). Information in that repository was provided by the original developer or other third parties and, unless expressly stated otherwise, has not been independently verified by Arm.

### Licenses and Third-Party Terms

Use of the Original Model and the Optimized Model is subject to the applicable licenses, usage restrictions and other terms identified above and in the relevant repositories. Publication of the Optimized Model does not grant any rights beyond those provided under the applicable license terms.

You are responsible for reviewing those terms and ensuring that your use of the Original Model and the Optimized Model is permitted.

### Purpose of this Release

The Optimized Model is provided as a reference implementation to demonstrate and evaluate execution and performance on Arm-based systems. It is not a production-ready or supported solution.

Arm’s publication of the Optimized Model does not constitute an endorsement or certification of the Original Model or a representation that the Optimized Model is suitable for production use or any particular purpose.

To the fullest extent permitted by applicable law (i) the Optimized Model is provided “as is.” Arm makes no representations or warranties that the Original Model, the Optimized Model or their outputs are accurate, safe, secure, non-infringing, legally compliant, suitable for production use or fit for any particular purpose; and (ii) Arm will not be liable for any loss or damage arising from or in connection with the Optimized Model, its use or its outputs.

You are responsible for independently evaluating the Optimized Model, its outputs and its suitability for your intended use, including compliance with applicable legal, regulatory, safety and security requirements.

Arm does not commit to provide ongoing support, maintenance or updates for the Optimized Model. Any use of or reliance on the Optimized Model or its outputs is at your own risk.
