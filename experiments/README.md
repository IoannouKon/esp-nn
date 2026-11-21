# ESP32-S3 pooling and Global Mean

This branch combines both ESP-NN optimizations and the ESP32-S3-EYE experiment records. The historical reports retain their original firmware revisions, comparison labels, configurations, and raw logs.

## Kernel implementations

| Name | Implementation | Historical label |
|---|---|---|
| **128-bit sliding-window INT8 max pooling** | Uses a 128-bit vector path for eligible aligned tensors and reuses vertical maxima for eligible stride-1 3×3 and 5×5 windows. | Opt1 + Opt2 |
| **16-lane QACC INT8 Global Mean** | Accumulates 16 channels per QACC block for eligible tensors and keeps the original fallback. | EXP-MEAN |

ESP-TFLite Micro needs the guarded research MEAN adapter to call QACC. The production ESP-NN kernel can also be tested directly through the ESP-NN benchmark harness.

## Benchmark reports

| Experiment | Evidence |
|---|---|
| Official ESP-NN global-mean benchmark and correctness | [EXP-MEAN board results](exp-mean/results/RESULTS.md) |
| Extended 90-configuration sweep | [42 Global Mean and 48 max-pool shapes](extended-s3-shape-sweep/results/analysis/RESULTS.md) |
| Frozen MNIST max-pool evaluation | [Full-CNN max-pool benchmark](full-cnn-opt2/FULL_CNN_OPT2_RESULTS.md) |
| Frozen MNIST EXP-MEAN control | [Stock, max-pool and EXP-MEAN comparison](mnist-exp-mean/results/MNIST_EXP_MEAN_RESULTS.md) |
| Earlier multi-CNN study | [Custom CNNs and external pretrained references](multi-cnn/results/CNN_RESULTS.md) |
| Main multi-model study | [Original 13-model report](full-cnn-multi-model/results/CNN_RESULTS.md) |
| Latest multi-model study | [15 CNNs, isolated MEAN timings, and additional correctness inputs](full-cnn-multi-model/extension/results/CNN_RESULTS.md) |

Use the latest 15-model report for the consolidated end-to-end comparison. Each experimental directory contains its own raw captures, settings, and replay instructions.
