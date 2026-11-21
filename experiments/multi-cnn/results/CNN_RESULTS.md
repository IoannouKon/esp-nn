# ESP32-S3-EYE multi-CNN benchmark

**Result.** Opt1+Opt2 improved every CNN that executed sliding max-pool in the nine-model core matrix. EXP-MEAN was mixed despite verified QACC dispatch and exact outputs. Combined delivered five wins against stock and one incremental win against Opt1+Opt2. All four pretrained graphs were timing controls for these two changes.

- **Opt1+Opt2** won on frozen MNIST and four CIFAR-10 CNNs. Latency fell by 2.57–10.73% on those five models. The best standalone result was CIFAR-10 max5, 3,527.0 → 3,148.5 µs, 1.1202×. The other seven models were neutral.
- **EXP-MEAN** improved depthwise_both by 1.20%, from 5,291.25 to 5,228.0 µs. It slowed mean_only by 2.30% and both by 2.72%. The actual QACC path ran in all three. Some no-dispatch controls also shifted by over 1%, so these whole-firmware changes alone cannot isolate the mean kernel's share of the timing difference.
- **Combined** was 2.41% faster than Opt1+Opt2 on depthwise_both and within 1% on both and mean_only. The largest Combined-versus-stock reduction was 11.17% on max5. That model exercised only the max-pool change.
- **Pretrained controls.** Person Detection, MobileNetV2, MobileNetV3-Small and EfficientNet-Lite0 completed all four configurations. They exercised neither target optimization, and all five comparisons were neutral for these models. MobileNetV3-Small had a separate baseline output-fidelity issue described below.
- **Memory.** Actual tensor-arena use was identical across the four builds for every model. The core flash image grew by 592 bytes for Opt1+Opt2, 480 bytes for EXP-MEAN and 1,312 bytes for Combined.
- **Upstream assessment.** Opt2 is a reasonable isolated ESP-NN PR candidate given the repeatable wins on every exercised full graph and the previously verified kernel tests. EXP-MEAN merits further investigation before submission because the runtime bridge is required and the full-inference outcomes are mixed.

Four ESP-NN builds share the same pinned ESP-TFLite Micro runtime, guarded MEAN adapter and frozen model inputs. Stock uses Espressif's optimized ESP32-S3 ESP-NN integration, including the stock max-pool and mean routines.

## Overall outcomes

12 of 12 models completed all eight qualified physical timing boots. These models contributed 2,880 timed inferences. Full fixed-input outputs matched across all four variants for 12 models.

| Comparison | WIN | LOSS | NEUTRAL | SKIP | INCONCLUSIVE |
|---|---:|---:|---:|---:|---:|
| stock → opt2 | 5 | 0 | 7 | 0 | 0 |
| stock → mean | 1 | 2 | 6 | 0 | 3 |
| stock → combined | 5 | 0 | 5 | 0 | 2 |
| opt2 → combined | 1 | 0 | 9 | 0 | 2 |
| mean → combined | 5 | 0 | 6 | 0 | 1 |

## Invoke medians and actual dispatch

Times are microseconds. Each qualified cell uses two physical boots, five untimed warm-ups and 30 timed Invoke calls per boot. The reported value is the median of the two per-boot medians. The model input is identical on each timed inference. Dispatch counts come from separate Combined diagnostic boots. QACC helper counts include the reference comparison and synthetic-pattern trials.

| Model | Stock | Opt1+Opt2 | EXP-MEAN | Combined | Sliding assembly calls | QACC calls¹ | Complete output |
|---|---:|---:|---:|---:|---:|---:|---|
| mnist_fixed | 2923.5 | 2672 | 2948 | 2616 | 28 | 0 | exact |
| max3 | 3378 | 3140 | 3420 | 3125 | 16 | 0 | exact |
| max5 | 3527 | 3148.5 | 3569 | 3133 | 16 | 0 | exact |
| mean_only | 3277.75 | 3285.75 | 3353 | 3281 | 0 | 14 | exact |
| both | 3779.25 | 3500.75 | 3882 | 3530.75 | 32 | 14 | exact |
| depthwise_both | 5291.25 | 5155.5 | 5228 | 5031.25 | 16 | 14 | exact |
| avg_control | 3476 | 3448.5 | 3400 | 3381 | 0 | 0 | exact |
| neutral_control | 3091 | 3086.25 | 3077 | 3058 | 0 | 0 | exact |
| person_detection | 59468 | 59347.5 | 59282.5 | 59126.2 | 0 | 0 | exact |
| mobilenet_v2 | 2.11754e+06 | 2.11672e+06 | 2.11656e+06 | 2.11711e+06 | 0 | 0 | exact |
| mobilenet_v3_small | 616682 | 616694 | 617015 | 617104 | 0 | 0 | exact |
| efficientnet_lite0 | 3.00163e+06 | 3.0017e+06 | 3.00147e+06 | 3.00181e+06 | 0 | 0 | exact |

¹ A supported 32-channel MEAN invokes two 16-lane blocks in an ordinary inference. The diagnostic reported 14 calls per MEAN layer because it also ran six comparison patterns. Each of the three MEAN tensors matched both TFLite Micro reference routes in all six comparisons.

## All model comparisons

A time reduction greater than 1% crosses the WIN threshold; a time increase greater than 1% crosses the LOSS threshold. The verdict also checks whether the targeted path ran and whether the paired boot medians agree on the direction. Two boots describe the observed spread.

| Model | Comparison | Speedup | Time reduction | Threshold | Verdict | Notes |
|---|---|---:|---:|---|---|---|
| mnist_fixed | stock → opt2 | 1.0941× | +8.603% | WIN | WIN |  |
| mnist_fixed | stock → mean | 0.9917× | -0.838% | NEUTRAL | NEUTRAL |  |
| mnist_fixed | stock → combined | 1.1175× | +10.518% | WIN | WIN |  |
| mnist_fixed | opt2 → combined | 1.0214× | +2.096% | WIN | INCONCLUSIVE | threshold crossed without a targeted path |
| mnist_fixed | mean → combined | 1.1269× | +11.262% | WIN | WIN |  |
| max3 | stock → opt2 | 1.0758× | +7.046% | WIN | WIN |  |
| max3 | stock → mean | 0.9877× | -1.243% | LOSS | INCONCLUSIVE | threshold crossed without a targeted path |
| max3 | stock → combined | 1.0810× | +7.490% | WIN | WIN |  |
| max3 | opt2 → combined | 1.0048× | +0.478% | NEUTRAL | NEUTRAL |  |
| max3 | mean → combined | 1.0944× | +8.626% | WIN | WIN |  |
| max5 | stock → opt2 | 1.1202× | +10.731% | WIN | WIN |  |
| max5 | stock → mean | 0.9882× | -1.191% | LOSS | INCONCLUSIVE | threshold crossed without a targeted path |
| max5 | stock → combined | 1.1258× | +11.171% | WIN | WIN |  |
| max5 | opt2 → combined | 1.0049× | +0.492% | NEUTRAL | NEUTRAL |  |
| max5 | mean → combined | 1.1392× | +12.216% | WIN | WIN |  |
| mean_only | stock → opt2 | 0.9976× | -0.244% | NEUTRAL | NEUTRAL |  |
| mean_only | stock → mean | 0.9776× | -2.296% | LOSS | LOSS |  |
| mean_only | stock → combined | 0.9990× | -0.099% | NEUTRAL | NEUTRAL |  |
| mean_only | opt2 → combined | 1.0014× | +0.145% | NEUTRAL | NEUTRAL |  |
| mean_only | mean → combined | 1.0219× | +2.147% | WIN | INCONCLUSIVE | threshold crossed without a targeted path |
| both | stock → opt2 | 1.0796× | +7.369% | WIN | WIN |  |
| both | stock → mean | 0.9735× | -2.719% | LOSS | LOSS |  |
| both | stock → combined | 1.0704× | +6.575% | WIN | WIN |  |
| both | opt2 → combined | 0.9915× | -0.857% | NEUTRAL | NEUTRAL |  |
| both | mean → combined | 1.0995× | +9.048% | WIN | WIN |  |
| depthwise_both | stock → opt2 | 1.0263× | +2.566% | WIN | WIN |  |
| depthwise_both | stock → mean | 1.0121× | +1.195% | WIN | WIN |  |
| depthwise_both | stock → combined | 1.0517× | +4.914% | WIN | WIN |  |
| depthwise_both | opt2 → combined | 1.0247× | +2.410% | WIN | WIN |  |
| depthwise_both | mean → combined | 1.0391× | +3.763% | WIN | WIN |  |
| avg_control | stock → opt2 | 1.0080× | +0.791% | NEUTRAL | NEUTRAL |  |
| avg_control | stock → mean | 1.0224× | +2.186% | WIN | INCONCLUSIVE | threshold crossed without a targeted path |
| avg_control | stock → combined | 1.0281× | +2.733% | WIN | INCONCLUSIVE | threshold crossed without a targeted path |
| avg_control | opt2 → combined | 1.0200× | +1.957% | WIN | INCONCLUSIVE | threshold crossed without a targeted path |
| avg_control | mean → combined | 1.0056× | +0.559% | NEUTRAL | NEUTRAL |  |
| neutral_control | stock → opt2 | 1.0015× | +0.154% | NEUTRAL | NEUTRAL |  |
| neutral_control | stock → mean | 1.0045× | +0.453% | NEUTRAL | NEUTRAL |  |
| neutral_control | stock → combined | 1.0108× | +1.068% | WIN | INCONCLUSIVE | threshold crossed without a targeted path |
| neutral_control | opt2 → combined | 1.0092× | +0.915% | NEUTRAL | NEUTRAL |  |
| neutral_control | mean → combined | 1.0062× | +0.617% | NEUTRAL | NEUTRAL |  |
| person_detection | stock → opt2 | 1.0020× | +0.203% | NEUTRAL | NEUTRAL |  |
| person_detection | stock → mean | 1.0031× | +0.312% | NEUTRAL | NEUTRAL |  |
| person_detection | stock → combined | 1.0058× | +0.575% | NEUTRAL | NEUTRAL |  |
| person_detection | opt2 → combined | 1.0037× | +0.373% | NEUTRAL | NEUTRAL |  |
| person_detection | mean → combined | 1.0026× | +0.264% | NEUTRAL | NEUTRAL |  |
| mobilenet_v2 | stock → opt2 | 1.0004× | +0.039% | NEUTRAL | NEUTRAL |  |
| mobilenet_v2 | stock → mean | 1.0005× | +0.046% | NEUTRAL | NEUTRAL |  |
| mobilenet_v2 | stock → combined | 1.0002× | +0.020% | NEUTRAL | NEUTRAL |  |
| mobilenet_v2 | opt2 → combined | 0.9998× | -0.018% | NEUTRAL | NEUTRAL |  |
| mobilenet_v2 | mean → combined | 0.9997× | -0.026% | NEUTRAL | NEUTRAL |  |
| mobilenet_v3_small | stock → opt2 | 1.0000× | -0.002% | NEUTRAL | NEUTRAL |  |
| mobilenet_v3_small | stock → mean | 0.9995× | -0.054% | NEUTRAL | NEUTRAL |  |
| mobilenet_v3_small | stock → combined | 0.9993× | -0.068% | NEUTRAL | NEUTRAL |  |
| mobilenet_v3_small | opt2 → combined | 0.9993× | -0.066% | NEUTRAL | NEUTRAL |  |
| mobilenet_v3_small | mean → combined | 0.9999× | -0.014% | NEUTRAL | NEUTRAL |  |
| efficientnet_lite0 | stock → opt2 | 1.0000× | -0.002% | NEUTRAL | NEUTRAL |  |
| efficientnet_lite0 | stock → mean | 1.0001× | +0.005% | NEUTRAL | NEUTRAL |  |
| efficientnet_lite0 | stock → combined | 0.9999× | -0.006% | NEUTRAL | NEUTRAL |  |
| efficientnet_lite0 | opt2 → combined | 1.0000× | -0.004% | NEUTRAL | NEUTRAL |  |
| efficientnet_lite0 | mean → combined | 0.9999× | -0.011% | NEUTRAL | NEUTRAL |  |

## Boot variation and arena usage

Each boot entry is median [minimum, maximum] in microseconds. Extra inputs are checked outside the timing loop. The JSON includes every individual measurement and complete output tensor.

| Model | Firmware | Boot 1 | Boot 2 | PSRAM arena use, bytes |
|---|---|---|---|---:|
| mnist_fixed | stock | 2923.5 [2923, 2929] | 2923.5 [2923, 2929] | 28396 |
| mnist_fixed | opt2 | 2672 [2659, 2677] | 2672 [2658, 2677] | 28396 |
| mnist_fixed | mean | 2948 [2947, 2953] | 2948 [2947, 2953] | 28396 |
| mnist_fixed | combined | 2616 [2616, 2635] | 2616 [2616, 2636] | 28396 |
| max3 | stock | 3378 [3366, 3383] | 3378 [3366, 3383] | 29724 |
| max3 | opt2 | 3140 [3139, 3145] | 3140 [3139, 3145] | 29724 |
| max3 | mean | 3420 [3419, 3426] | 3420 [3419, 3425] | 29724 |
| max3 | combined | 3125 [3109, 3130] | 3125 [3108, 3130] | 29724 |
| max5 | stock | 3527 [3515, 3533] | 3527 [3515, 3532] | 29724 |
| max5 | opt2 | 3148 [3148, 3154] | 3149 [3148, 3154] | 29724 |
| max5 | mean | 3569 [3568, 3575] | 3569 [3568, 3575] | 29724 |
| max5 | combined | 3133 [3118, 3139] | 3133 [3117, 3138] | 29724 |
| mean_only | stock | 3278 [3276, 3292] | 3277.5 [3276, 3292] | 30364 |
| mean_only | opt2 | 3285.5 [3276, 3292] | 3286 [3276, 3292] | 30364 |
| mean_only | mean | 3353 [3337, 3359] | 3353 [3337, 3359] | 30364 |
| mean_only | combined | 3281 [3265, 3287] | 3281 [3265, 3287] | 30364 |
| both | stock | 3779.5 [3777, 3790] | 3779 [3777, 3791] | 30588 |
| both | opt2 | 3501 [3491, 3507] | 3500.5 [3491, 3506] | 30588 |
| both | mean | 3882 [3876, 3892] | 3882 [3876, 3892] | 30588 |
| both | combined | 3531 [3516, 3538] | 3530.5 [3516, 3538] | 30588 |
| depthwise_both | stock | 5292 [5277, 5338] | 5290.5 [5278, 5338] | 18764 |
| depthwise_both | opt2 | 5155.5 [5150, 5183] | 5155.5 [5150, 5178] | 18764 |
| depthwise_both | mean | 5228 [5218, 5241] | 5228 [5218, 5240] | 18764 |
| depthwise_both | combined | 5031.5 [5027, 5036] | 5031 [5027, 5036] | 18764 |
| avg_control | stock | 3476 [3475, 3481] | 3476 [3475, 3481] | 29724 |
| avg_control | opt2 | 3448 [3436, 3454] | 3449 [3434, 3454] | 29724 |
| avg_control | mean | 3400 [3391, 3405] | 3400 [3392, 3405] | 29724 |
| avg_control | combined | 3381 [3371, 3387] | 3381 [3372, 3387] | 29724 |
| neutral_control | stock | 3091 [3090, 3096] | 3091 [3090, 3096] | 29612 |
| neutral_control | opt2 | 3086 [3086, 3092] | 3086.5 [3086, 3092] | 29612 |
| neutral_control | mean | 3077 [3076, 3082] | 3077 [3076, 3082] | 29612 |
| neutral_control | combined | 3058 [3058, 3064] | 3058 [3058, 3064] | 29612 |
| person_detection | stock | 59468 [59449, 59472] | 59468 [59451, 59474] | 120988 |
| person_detection | opt2 | 59348 [59337, 59360] | 59347 [59335, 59361] | 120988 |
| person_detection | mean | 59283 [59277, 59310] | 59282 [59276, 59308] | 120988 |
| person_detection | combined | 59126 [59120, 59186] | 59126.5 [59119, 59190] | 120988 |
| mobilenet_v2 | stock | 2.11754e+06 [2.11753e+06, 2.11759e+06] | 2.11754e+06 [2.11753e+06, 2.11759e+06] | 2607164 |
| mobilenet_v2 | opt2 | 2.11672e+06 [2.11671e+06, 2.11674e+06] | 2.11672e+06 [2.11671e+06, 2.11674e+06] | 2607164 |
| mobilenet_v2 | mean | 2.11656e+06 [2.11654e+06, 2.11663e+06] | 2.11656e+06 [2.11654e+06, 2.11663e+06] | 2607164 |
| mobilenet_v2 | combined | 2.11711e+06 [2.1171e+06, 2.11713e+06] | 2.11711e+06 [2.1171e+06, 2.11713e+06] | 2607164 |
| mobilenet_v3_small | stock | 616682 [616642, 616711] | 616682 [616642, 616711] | 3290812 |
| mobilenet_v3_small | opt2 | 616694 [616647, 616738] | 616694 [616647, 616738] | 3290812 |
| mobilenet_v3_small | mean | 617015 [616981, 617023] | 617015 [616981, 617023] | 3290812 |
| mobilenet_v3_small | combined | 617104 [617075, 617133] | 617104 [617075, 617133] | 3290812 |
| efficientnet_lite0 | stock | 3.00163e+06 [3.00161e+06, 3.00163e+06] | 3.00163e+06 [3.00161e+06, 3.00163e+06] | 1717292 |
| efficientnet_lite0 | opt2 | 3.0017e+06 [3.00168e+06, 3.00175e+06] | 3.0017e+06 [3.00168e+06, 3.00175e+06] | 1717292 |
| efficientnet_lite0 | mean | 3.00147e+06 [3.00144e+06, 3.00149e+06] | 3.00147e+06 [3.00144e+06, 3.00149e+06] | 1717292 |
| efficientnet_lite0 | combined | 3.00181e+06 [3.0018e+06, 3.00183e+06] | 3.00181e+06 [3.0018e+06, 3.00183e+06] | 1717292 |

## Model and output inventory

| Model | Input → output | MAX_POOL / MEAN | Host INT8 top-1¹ | Extra board inputs | Desktop reference exact² |
|---|---|---:|---:|---:|---:|
| avg_control | INT8 [1, 32, 32, 3] → INT8 [1, 10] | 0 / 0 | 33.2% | 6 | 7/7 |
| both | INT8 [1, 32, 32, 3] → INT8 [1, 1, 1, 10] | 2 / 1 | 24.3% | 6 | 7/7 |
| depthwise_both | INT8 [1, 32, 32, 3] → INT8 [1, 1, 1, 10] | 1 / 1 | 19.2% | 6 | 7/7 |
| efficientnet_lite0 | UINT8 [1, 224, 224, 3] → UINT8 [1, 1000] | 0 / 0 | — | 0 | 1/1 |
| max3 | INT8 [1, 32, 32, 3] → INT8 [1, 10] | 1 / 0 | 38.5% | 6 | 7/7 |
| max5 | INT8 [1, 32, 32, 3] → INT8 [1, 10] | 1 / 0 | 39.8% | 6 | 7/7 |
| mean_only | INT8 [1, 32, 32, 3] → INT8 [1, 1, 1, 10] | 0 / 1 | 20.6% | 6 | 7/7 |
| mnist_fixed | INT8 [1, 28, 28, 1] → INT8 [1, 10] | 2 / 0 | — | 6 | 7/7 |
| mobilenet_v2 | INT8 [1, 3, 224, 224] → INT8 [1, 1000] | 0 / 0 | — | 0 | 0/1 |
| mobilenet_v3_small | INT8 [1, 3, 224, 224] → INT8 [1, 1000] | 0 / 0 | — | 0 | 0/1 |
| neutral_control | INT8 [1, 32, 32, 3] → INT8 [1, 10] | 0 / 0 | 38.8% | 6 | 7/7 |
| person_detection | INT8 [1, 96, 96, 1] → INT8 [1, 2] | 0 / 0 | — | 0 | — |

Desktop-versus-board fixed-input differences in quantized output units

- mobilenet_v2 — Desktop reference: 987 elements, max 121. Desktop default: 538 elements, max 4.
- mobilenet_v3_small — Desktop reference: 1000 elements, max 209. Desktop default: 1000 elements, max 213.

¹ Custom CIFAR-10 models were trained for one epoch using the kit defaults. This is desktop TFLite classification using actual INT8 logits on the first 1,000 held-out test images. It is distinct from board correctness.

² Desktop TFLite BUILTIN_REF and ESP-TFLite Micro may use different integer convolution and reduction paths. The board-to-board gate compares all output bytes. The on-board MEAN test compares its actual intermediates directly with the pinned TFLite Micro reference and original registration.

Person Detection's original model was rejected by the desktop TFLite importer's affine quantization check for several legacy bias tensors. Its untouched firmware model is checked on ESP-TFLite Micro.

The MobileNetV3-Small artifact is the public historical INT8 channelwise release. The provider withdrew that export after finding accuracy degradation. Treat its result as a timing observation on a known architecture. The exported graph uses average pooling and has no MEAN or MAX_POOL_2D nodes.

## Untimed MobileNet fidelity check

A separate on-board diagnostic compiled out ESP-NN calls guarded by the pinned TFLite Micro runtime. It reused the identical models and fixed inputs. The slow reference invokes completed after nonfatal idle-task watchdog reports, which are confined to this diagnostic log.

MobileNetV2's 1,000 output bytes matched the optimized stock board output exactly. Its fixed-input difference from desktop default TFLite was at most four quantized units.

MobileNetV3-Small saturated 999 of 1,000 logits in optimized stock and 999 of 1,000 in the reference diagnostic. The two on-board routes differed at 423 logits, with a maximum absolute difference of 255 quantized units. The underlying operator fault was not isolated. All four timed outputs agreed with each other, and neither study optimization was called by that graph. This timing control therefore gives no evidence of MobileNetV3-Small classification fidelity.

[Complete reference serial log](logs/suite_mobiles/tflm-reference-diagnostic.log) · [Exact comparison data](diagnostics/stock_tflm_reference_results.json)

## Evidence

- [Operator versions, provenance, tensor shapes and SHA256 hashes](manifest.json)
- [Individual measurements and exact output bytes](comparison.json)
- [All comparisons as CSV](comparison.csv)
- [Raw serial and flash logs](logs/)
- [Build and configuration evidence](build_provenance.md) and [firmware sizes](firmware_sizes.md)
- [MEAN integration source and reference arithmetic](mean_bridge_patch/README.md)
- [MobileNetV3-Small artifact](https://huggingface.co/litert-community/MobileNet-v3-small/commit/77f13855abb1d843015ff3605e5748b960ffe7dd) and [upstream accuracy finding](https://huggingface.co/litert-community/MobileNet-v3-small/commit/16a1a16018be8bf3db791b816387563f2204d756)
