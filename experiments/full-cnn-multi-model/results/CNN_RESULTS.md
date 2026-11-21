# ESP32-S3-EYE full-CNN benchmark

## Target-kernel verdicts

- Opt1+Opt2 won on 5 of 5 models with verified sliding dispatch. Latency fell 6.131–10.124%. max5 had the largest reduction at 1.1126× stock speed.
- both called QACC. EXP-MEAN reduced latency by +1.375% versus stock. Combined reduced latency by +2.003% versus Opt1+Opt2.
- depthwise_both called QACC. EXP-MEAN reduced latency by +2.934% versus stock. Combined reduced latency by +3.856% versus Opt1+Opt2.
- mean_only called QACC. EXP-MEAN reduced latency by +2.393% versus stock. Combined reduced latency by +3.021% versus Opt1+Opt2.
- The Mean-only firmware also shifted timings by more than 1% on custom controls with no MEAN operator. The study verifies QACC dispatch and correctness. These control shifts limit how precisely the measured full-app gains can be attributed to QACC alone.
- The opt2 firmware ran mean_only 1.453% slower than stock. The changed kernel had no calls in that graph.
- Every stock comparison with verified target dispatch met the study's win rule. The evidence supports a workload-specific claim about eligible pooling and MEAN graphs.
- The stock and Combined reference stress tests matched on 15,408 complete tensors and 354,096 output bytes in total. The three per-model MEAN probes also run the actual intermediate through both TFLite Micro reference routes.
- All seven pretrained models completed inference. Neither target kernel executed on those graphs, and their largest absolute median change was 0.583%.

7 pinned upstream pretrained CNNs and 6 local CNNs completed the four-build comparison, for 3,120 accepted timed inferences. All accepted models returned identical complete output tensors across both boots and all four firmware builds. No models were skipped.

The inputs for the upstream pretrained models are deterministic raw INT8 samples for latency and output parity. This experiment measures no classifier accuracy on those inputs.

## Model results

| Model | Workload | Outcome | Arena used (bytes) | Sliding calls per pool | QACC |
|---|---|---|---:|---|---|
| mlperf_cifar10_resnet8 | pretrained | PASS | 206844 | — | control only / no QACC |
| mlperf_vww_mobilenet | pretrained | PASS | 120940 | — | control only / no QACC |
| tflm_person_detection | pretrained | PASS | 120988 | — | control only / no QACC |
| mlperf_kws_dscnn | pretrained | PASS | 35516 | — | control only / no QACC |
| mlperf_cifar10_resnet6 | pretrained | PASS | 469148 | — | control only / no QACC |
| mlperf_vww_14block | pretrained | PASS | 196412 | — | control only / no QACC |
| mlperf_vww_20block | pretrained | PASS | 202476 | — | control only / no QACC |
| mnist_fixed | frozen MNIST control | PASS | 28396 | 14, 14 | control only / no QACC |
| max3 | custom CIFAR-10 | PASS | 29724 | 16 | control only / no QACC |
| max5 | custom CIFAR-10 | PASS | 29724 | 16 | control only / no QACC |
| mean_only | custom CIFAR-10 | PASS | 29660 | — | verified |
| both | custom CIFAR-10 | PASS | 29884 | 16, 16 | verified |
| depthwise_both | custom CIFAR-10 | PASS | 18060 | 16 | verified |

## Complete inference timing and cycles

Each value is the median of the two per-boot medians. Every boot ran five untimed warm-ups and 30 timed inferences. The time comes from esp_timer_get_time; cycles come from the same-core hardware cycle counter around the same invocation and timer reads. Cycle deltas can include interrupts and scheduler overhead.

| Model | Build | Median µs | Median cycles | Time speedup | Cycle speedup | Time reduction | Sample ranges µs / cycles | Verdict |
|---|---|---:|---:|---:|---:|---:|---|---|
| mlperf_cifar10_resnet8 | stock | 347673 | 8.34418e+07 | 1.0000× | 1.0000× | +0.000% | 347628–347688 / 83431447–83445544 | BASELINE |
| mlperf_cifar10_resnet8 | opt2 | 347385 | 8.33727e+07 | 1.0008× | 1.0008× | +0.083% | 347339–347390 / 83361829–83373970 | CONTROL ONLY |
| mlperf_cifar10_resnet8 | mean | 347369 | 8.33689e+07 | 1.0009× | 1.0009× | +0.087% | 347328–347381 / 83359519–83371852 | CONTROL ONLY |
| mlperf_cifar10_resnet8 | combined | 347968 | 8.35127e+07 | 0.9991× | 0.9991× | -0.085% | 347918–347981 / 83501383–83515696 | CONTROL ONLY |
| mlperf_vww_mobilenet | stock | 66842.2 | 1.60426e+07 | 1.0000× | 1.0000× | +0.000% | 66831–66851 / 16039834–16044670 | BASELINE |
| mlperf_vww_mobilenet | opt2 | 67029.8 | 1.60876e+07 | 0.9972× | 0.9972× | -0.281% | 67011–67042 / 16083553–16090432 | CONTROL ONLY |
| mlperf_vww_mobilenet | mean | 67073.2 | 1.60981e+07 | 0.9966× | 0.9966× | -0.346% | 67064–67084 / 16095721–16100425 | CONTROL ONLY |
| mlperf_vww_mobilenet | combined | 66759.5 | 1.60227e+07 | 1.0012× | 1.0012× | +0.124% | 66736–66768 / 16017145–16024462 | CONTROL ONLY |
| tflm_person_detection | stock | 59054.8 | 1.41736e+07 | 1.0000× | 1.0000× | +0.000% | 59050–59062 / 14172340–14175295 | BASELINE |
| tflm_person_detection | opt2 | 59227.8 | 1.42151e+07 | 0.9971× | 0.9971× | -0.293% | 59183–59250 / 14204075–14220577 | CONTROL ONLY |
| tflm_person_detection | mean | 59399.2 | 1.42564e+07 | 0.9942× | 0.9942× | -0.583% | 59389–59409 / 14253751–14258554 | CONTROL ONLY |
| tflm_person_detection | combined | 58897 | 1.41358e+07 | 1.0027× | 1.0027× | +0.267% | 58850–58921 / 14124146–14141539 | CONTROL ONLY |
| mlperf_kws_dscnn | stock | 17476.8 | 4.19492e+06 | 1.0000× | 1.0000× | +0.000% | 17406–17548 / 4178071–4211863 | BASELINE |
| mlperf_kws_dscnn | opt2 | 17434 | 4.18454e+06 | 1.0025× | 1.0025× | +0.245% | 17351–17500 / 4164883–4200265 | CONTROL ONLY |
| mlperf_kws_dscnn | mean | 17469.5 | 4.19314e+06 | 1.0004× | 1.0004× | +0.041% | 17401–17541 / 4176724–4210126 | CONTROL ONLY |
| mlperf_kws_dscnn | combined | 17425 | 4.18234e+06 | 1.0030× | 1.0030× | +0.296% | 17355–17484 / 4166038–4196434 | CONTROL ONLY |
| mlperf_cifar10_resnet6 | stock | 3.46494e+06 | 8.31585e+08 | 1.0000× | 1.0000× | +0.000% | 3464902–3464999 / 831577221–831599821 | BASELINE |
| mlperf_cifar10_resnet6 | opt2 | 3.45708e+06 | 8.29701e+08 | 1.0023× | 1.0023× | +0.227% | 3457073–3457095 / 829698135–829703139 | CONTROL ONLY |
| mlperf_cifar10_resnet6 | mean | 3.45703e+06 | 8.29688e+08 | 1.0023× | 1.0023× | +0.228% | 3456994–3457036 / 829679778–829688761 | CONTROL ONLY |
| mlperf_cifar10_resnet6 | combined | 3.46481e+06 | 8.31555e+08 | 1.0000× | 1.0000× | +0.004% | 3464801–3464813 / 831552669–831555600 | CONTROL ONLY |
| mlperf_vww_14block | stock | 170984 | 4.10365e+07 | 1.0000× | 1.0000× | +0.000% | 170950–170995 / 41028409–41039218 | BASELINE |
| mlperf_vww_14block | opt2 | 170775 | 4.09866e+07 | 1.0012× | 1.0012× | +0.122% | 170743–170780 / 40978873–40987972 | CONTROL ONLY |
| mlperf_vww_14block | mean | 170823 | 4.09978e+07 | 1.0009× | 1.0009× | +0.094% | 170788–170841 / 40989751–41002147 | CONTROL ONLY |
| mlperf_vww_14block | combined | 171006 | 4.10423e+07 | 0.9999× | 0.9999× | -0.013% | 170979–171008 / 41035756–41043049 | CONTROL ONLY |
| mlperf_vww_20block | stock | 254138 | 6.09936e+07 | 1.0000× | 1.0000× | +0.000% | 254110–254155 / 60986953–60997558 | BASELINE |
| mlperf_vww_20block | opt2 | 254252 | 6.10208e+07 | 0.9996× | 0.9996× | -0.045% | 254217–254255 / 61012696–61021798 | CONTROL ONLY |
| mlperf_vww_20block | mean | 254301 | 6.10326e+07 | 0.9994× | 0.9994× | -0.064% | 254267–254317 / 61024882–61036384 | CONTROL ONLY |
| mlperf_vww_20block | combined | 254032 | 6.09684e+07 | 1.0004× | 1.0004× | +0.042% | 254001–254039 / 60961069–60970171 | CONTROL ONLY |
| mnist_fixed | stock | 3005.75 | 721570 | 1.0000× | 1.0000× | +0.000% | 2985–3041 / 716651–730465 | BASELINE |
| mnist_fixed | opt2 | 2740 | 657698 | 1.0970× | 1.0971× | +8.841% | 2740–2770 / 657698–665217 | WIN |
| mnist_fixed | mean | 3006 | 721570 | 0.9999× | 1.0000× | -0.008% | 2985–3042 / 716651–730465 | CONTROL ONLY |
| mnist_fixed | combined | 2743.5 | 658673 | 1.0956× | 1.0955× | +8.725% | 2743–2774 / 658673–666192 | WIN |
| max3 | stock | 3468 | 832500 | 1.0000× | 1.0000× | +0.000% | 3468–3470 / 832499–833283 | BASELINE |
| max3 | opt2 | 3242 | 778335 | 1.0697× | 1.0696× | +6.517% | 3242–3242 / 778335–778827 | WIN |
| max3 | mean | 3378 | 811051 | 1.0266× | 1.0265× | +2.595% | 3378–3391 / 811051–814339 | CONTROL ONLY |
| max3 | combined | 3141 | 754216 | 1.1041× | 1.1038× | +9.429% | 3135–3153 / 752881–757027 | WIN |
| max5 | stock | 3615 | 867864 | 1.0000× | 1.0000× | +0.000% | 3615–3617 / 867863–868647 | BASELINE |
| max5 | opt2 | 3249 | 779982 | 1.1126× | 1.1127× | +10.124% | 3249–3250 / 779982–780474 | WIN |
| max5 | mean | 3525 | 846442 | 1.0255× | 1.0253× | +2.490% | 3525–3538 / 846442–849730 | CONTROL ONLY |
| max5 | combined | 3148 | 755863 | 1.1483× | 1.1482× | +12.918% | 3142–3160 / 754528–758674 | WIN |
| mean_only | stock | 3165 | 759795 | 1.0000× | 1.0000× | +0.000% | 3165–3166 / 759795–760578 | BASELINE |
| mean_only | opt2 | 3211 | 770865 | 0.9857× | 0.9856× | -1.453% | 3211–3214 / 770865–771876 | CONTROL ONLY |
| mean_only | mean | 3089.25 | 741800 | 1.0245× | 1.0243× | +2.393% | 3083–3094 / 740557–742903 | WIN |
| mean_only | combined | 3114 | 747856 | 1.0164× | 1.0160× | +1.611% | 3109–3126 / 746737–750667 | WIN |
| both | stock | 3617.25 | 868568 | 1.0000× | 1.0000× | +0.000% | 3612–3622 / 867507–869593 | BASELINE |
| both | opt2 | 3270.5 | 785118 | 1.1060× | 1.1063× | +9.586% | 3270–3283 / 785118–788175 | WIN |
| both | mean | 3567.5 | 856645 | 1.0139× | 1.0139× | +1.375% | 3567–3611 / 856645–867148 | WIN |
| both | combined | 3205 | 769552 | 1.1286× | 1.1287× | +11.397% | 3205–3219 / 769552–773170 | WIN |
| depthwise_both | stock | 4958.5 | 1.19102e+06 | 1.0000× | 1.0000× | +0.000% | 4946–4959 / 1188037–1191018 | BASELINE |
| depthwise_both | opt2 | 4654.5 | 1.11747e+06 | 1.0653× | 1.0658× | +6.131% | 4643–4660 / 1115040–1118804 | WIN |
| depthwise_both | mean | 4813 | 1.15571e+06 | 1.0302× | 1.0306× | +2.934% | 4811–4826 / 1155189–1158828 | WIN |
| depthwise_both | combined | 4475 | 1.0745e+06 | 1.1080× | 1.1084× | +9.751% | 4459–4479 / 1070575–1075441 | WIN |

Timing changes in control-only rows are preserved in the table and raw data. A control-only comparison has no verified execution of the changed kernel. The numerical cutoff is a time reduction greater than 1% for a win and a time increase greater than 1% for a loss. The two paired boot medians must agree on direction.

## Combined versus individual builds

The verdict describes the effect of adding the other optimization. A control-only row preserves the measured difference when the additional kernel had no verified call.

| Model | From Opt1+Opt2 | Verdict | From EXP-MEAN | Verdict |
|---|---:|---|---:|---|
| mlperf_cifar10_resnet8 | 0.9983× / -0.168% | CONTROL ONLY | 0.9983× / -0.172% | CONTROL ONLY |
| mlperf_vww_mobilenet | 1.0041× / +0.403% | CONTROL ONLY | 1.0047× / +0.468% | CONTROL ONLY |
| tflm_person_detection | 1.0056× / +0.558% | CONTROL ONLY | 1.0085× / +0.846% | CONTROL ONLY |
| mlperf_kws_dscnn | 1.0005× / +0.052% | CONTROL ONLY | 1.0026× / +0.255% | CONTROL ONLY |
| mlperf_cifar10_resnet6 | 0.9978× / -0.224% | CONTROL ONLY | 0.9978× / -0.225% | CONTROL ONLY |
| mlperf_vww_14block | 0.9987× / -0.135% | CONTROL ONLY | 0.9989× / -0.107% | CONTROL ONLY |
| mlperf_vww_20block | 1.0009× / +0.086% | CONTROL ONLY | 1.0011× / +0.106% | CONTROL ONLY |
| mnist_fixed | 0.9987× / -0.128% | CONTROL ONLY | 1.0957× / +8.733% | WIN |
| max3 | 1.0322× / +3.115% | CONTROL ONLY | 1.0755× / +7.016% | WIN |
| max5 | 1.0321× / +3.109% | CONTROL ONLY | 1.1198× / +10.695% | WIN |
| mean_only | 1.0312× / +3.021% | WIN | 0.9920× / -0.801% | CONTROL ONLY |
| both | 1.0204× / +2.003% | WIN | 1.1131× / +10.161% | WIN |
| depthwise_both | 1.0401× / +3.856% | WIN | 1.0755× / +7.023% | WIN |

## Binary size and memory

App image sizes come from the verified esptool flash write. Arena usage stayed identical across the eight boots of each model. The JSON and CSV provide stack high-water marks for each firmware.

| Model | Arena used (bytes) | Stock image (bytes) | Opt1+Opt2 Δ bytes | EXP-MEAN Δ bytes | Combined Δ bytes |
|---|---:|---:|---:|---:|---:|
| mlperf_cifar10_resnet8 | 206,844 | 960,672 | +544 | -48 | +704 |
| mlperf_vww_mobilenet | 120,940 | 806,512 | +544 | -48 | +704 |
| tflm_person_detection | 120,988 | 755,360 | +544 | -48 | +704 |
| mlperf_kws_dscnn | 35,516 | 500,000 | +544 | -48 | +720 |
| mlperf_cifar10_resnet6 | 469,148 | 1,247,712 | +592 | +0 | +592 |
| mlperf_vww_14block | 196,412 | 1,461,792 | +544 | -48 | +704 |
| mlperf_vww_20block | 202,476 | 1,438,944 | +544 | -48 | +704 |
| mnist_fixed | 28,396 | 471,360 | +544 | -48 | +704 |
| max3 | 29,724 | 481,024 | +608 | +496 | +1,344 |
| max5 | 29,724 | 481,024 | +608 | +496 | +1,344 |
| mean_only | 29,660 | 462,304 | +656 | +528 | +1,216 |
| both | 29,884 | 462,304 | +656 | +528 | +1,216 |
| depthwise_both | 18,060 | 458,400 | +608 | +496 | +1,344 |

## Graph and data provenance

| Model | Operator counts | Model SHA-256 | Input SHA-256 | Desktop default¹ | Desktop reference¹ |
|---|---|---|---|---|---|
| mlperf_cifar10_resnet8 | CONV_2D ×9, ADD ×3, AVERAGE_POOL_2D ×1, RESHAPE ×1, FULLY_CONNECTED ×1, SOFTMAX ×1 | dc27dcd823f5665533352f7da516b0c9bc6f089914b8283782e55961b3423fcf | 8e8c834bd5b38b8e63cbf6f03936a29c02d8b98510a419160940021e79618b91 | exact | exact |
| mlperf_vww_mobilenet | CONV_2D ×14, DEPTHWISE_CONV_2D ×13, AVERAGE_POOL_2D ×1, RESHAPE ×1, FULLY_CONNECTED ×1, SOFTMAX ×1 | 597a384c8c2c8a1276f04702f25013b7838f2f814f1ca7c174d295b73e3d6b7b | 3c1bccd285611fec044b6f051a6316be1cdb3c9d827b119d9e049c189f63a2e1 | 2/2 differ, max Δ 1 | exact |
| tflm_person_detection | DEPTHWISE_CONV_2D ×14, CONV_2D ×14, AVERAGE_POOL_2D ×1, RESHAPE ×1, SOFTMAX ×1 | 808cfdfc0cf3a6fa6f6fa26bfa379ea97c16d5db7334637766e39c3408502e9d | 9de21494c27460b80d127cbfdf3711325552d88e87031320b630b4f809296abe | unavailable | unavailable |
| mlperf_kws_dscnn | CONV_2D ×5, DEPTHWISE_CONV_2D ×4, AVERAGE_POOL_2D ×1, RESHAPE ×1, FULLY_CONNECTED ×1, SOFTMAX ×1 | aeea436800704fce17b17292e4412630ad856e9d777c044c64ef748a880bd0ae | dae3e297eabf2d8cdf8918b5d9a38083142d0b7a5f38185a4f55f9c76f4f3cfc | 1/12 differ, max Δ 1 | exact |
| mlperf_cifar10_resnet6 | CONV_2D ×15, ADD ×6, AVERAGE_POOL_2D ×1, RESHAPE ×1, FULLY_CONNECTED ×1, SOFTMAX ×1 | 5c7e4053e5a941212ae4f00f82f1a790905cfb70489283af3d8f02ea8b917453 | 8e8c834bd5b38b8e63cbf6f03936a29c02d8b98510a419160940021e79618b91 | 3/10 differ, max Δ 21 | exact |
| mlperf_vww_14block | CONV_2D ×14, DEPTHWISE_CONV_2D ×13, AVERAGE_POOL_2D ×1, RESHAPE ×1, FULLY_CONNECTED ×1, SOFTMAX ×1 | 418957d510379f55f4798c606372a3e8828de596100407ecac693125c9d77d6f | 3c1bccd285611fec044b6f051a6316be1cdb3c9d827b119d9e049c189f63a2e1 | exact | exact |
| mlperf_vww_20block | CONV_2D ×20, DEPTHWISE_CONV_2D ×19, AVERAGE_POOL_2D ×1, RESHAPE ×1, FULLY_CONNECTED ×1, SOFTMAX ×1 | 73d3b8aa59c92badca8011e2c49277b28c4ce41456b213f47c42d3051ec7c0a5 | 3c1bccd285611fec044b6f051a6316be1cdb3c9d827b119d9e049c189f63a2e1 | 2/2 differ, max Δ 1 | exact |
| mnist_fixed | CONV_2D ×2, MAX_POOL_2D ×2, RESHAPE ×1, FULLY_CONNECTED ×1 | 163d2e5014411841e814e927967887ae4d42ae283b12116b55514a3f0daaef47 | 1f84c643695b1a774441f8f8b6a29ba99024fd234c0cfe98ba6095dc270077f8 | exact | exact |
| max3 | CONV_2D ×2, MAX_POOL_2D ×1, RESHAPE ×1, FULLY_CONNECTED ×1 | 6a457b7fb409fc0668379fbae4b6614223287ca7a8273ffe9f9770685824a04b | 9f2b799d8a7d23ea057764d98841e08038753212d8fcb06b4b8f28a859926511 | exact | exact |
| max5 | CONV_2D ×2, MAX_POOL_2D ×1, RESHAPE ×1, FULLY_CONNECTED ×1 | 719758439a3fc697f2f2533219dd64198656ef81794e5fc860dc013e023e37e9 | 9f2b799d8a7d23ea057764d98841e08038753212d8fcb06b4b8f28a859926511 | exact | exact |
| mean_only | CONV_2D ×2, MEAN ×1, FULLY_CONNECTED ×1 | f24283500ae7f9a377f8aa5bda5086ca81294d6e8bbfbbdca24be86010ffeecc | 9f2b799d8a7d23ea057764d98841e08038753212d8fcb06b4b8f28a859926511 | exact | exact |
| both | CONV_2D ×2, MAX_POOL_2D ×2, MEAN ×1, FULLY_CONNECTED ×1 | 2a1d57d833b9a43ba281e53a09b8b5bdec7aab5139d3aaf97e57ba93e0b3153d | 9f2b799d8a7d23ea057764d98841e08038753212d8fcb06b4b8f28a859926511 | exact | exact |
| depthwise_both | CONV_2D ×2, MAX_POOL_2D ×1, DEPTHWISE_CONV_2D ×1, MEAN ×1, FULLY_CONNECTED ×1 | c2b43e3633fb33a1b505cb2f579d4cad238f33284fbc82958edf6d1a8381ef45 | 9f2b799d8a7d23ea057764d98841e08038753212d8fcb06b4b8f28a859926511 | exact | exact |

¹ The experiment gates correctness on whole output parity across the four on-board builds. The desktop columns compare against TensorFlow Lite 2.15.1 with its default and BUILTIN_REF kernels. The exact differences describe runtime agreement for the fixed input. TensorFlow Lite 2.15.1 rejects the pinned Person Detection model's legacy affine metadata. Its input was generated from the unchanged model's schema. [Desktop reference outputs](desktop-reference.json)

## Dispatch and MEAN adapter

5 accepted graphs have measured sliding assembly calls in a separate diagnostic build. 3 accepted graphs have verified QACC execution. The seven pinned upstream graphs contain neither MAX_POOL_2D nor MEAN. Their timing differences cannot be attributed to either study optimization.

The pinned runtime's built-in MEAN operates within TFLite Micro. The optional graph-level bridge is restricted to the validated INT8 NHWC spatial reduction and shared among all four custom builds. [Adapter and quantization mapping](../integration/README.md) · [Diagnostic logs](diagnostics/)

On `both`, the separate Opt1+Opt2 firmware called the sliding assembly 16 times per pool layer and had zero QACC calls. The EXP-MEAN firmware had zero sliding calls and logged 14 QACC blocks during the diagnostic, including the extra reference comparisons. [Opt1+Opt2 probe](diagnostics/both/opt2-probe.log) · [EXP-MEAN probe](diagnostics/both/mean-probe.log)

## Setup and reproducibility

- ESP32-S3-EYE, USB Serial/JTAG on /dev/ttyACM0, one core at 240 MHz, 8 MiB octal PSRAM at 80 MHz. The kit config uses a 64 KiB, 8-way data cache, 64-byte cache lines, a 2 MiB aligned PSRAM tensor arena and an 8 KiB main task stack. Actual use and stack high-water marks are in the machine-readable data.
- ESP-IDF v5.5.1 at fcae32885b0296b32044cb99ecbdc50d98dddb83 and Xtensa GCC 14.2.0. ESP-TFLite Micro v1.4.3 at df8722334a80ceabc609c1e72968f417cd9437f1. IDF reports a dirty tree from unrelated pre-existing example edits. [IDF status](idf-revision.txt)
- Stock ESP-NN at ace42ac7721119cd543fc40ffe719e601fa8f20f. Opt1+Opt2 at edb003c6770491abb74766835f4c803b9d4f5a20. EXP-MEAN at 4bfa49c64a932f700688c2007a01d8ea1fa102ac. Combined overlays the exact two-file pooling patch on the detached EXP-MEAN tree. Stock uses Espressif's ESP32-S3 optimized backend through ESP-TFLite Micro's ESP-NN integration.
- The original firmware runner supplies both timers. The harness restores the frozen input before each Invoke because TFLM may reuse the input arena. The scheduler yield and output validation/printing stay outside the timed region. All captures reset the board after monitor attachment and verify the flashed ELF fingerprint.
- Per-model boot order is Stock, Opt2, Mean, Combined, Combined, Mean, Opt2, Stock. The 20-minute ceiling covers each serial capture. Build and flash run separately.
- The warm-up/steady-state harness and model bytes match across all implementations of each model. The compiled paths, ELF hashes, SDK config, boot data, build and flash logs are alongside each serial log.
- ResNet6 triggered the idle-task watchdog during the first trial. The archived trial is excluded from the comparison. Every accepted ResNet6 build uses a 20-second watchdog interval set before allocation and inference.

[Frozen upstream URLs](../PRETRAINED_MODELS.json) · [Replay commands](EXPERIMENT_COMMANDS.md) · [All comparisons](analysis/compare.csv) · [Revisions and compiler paths](provenance/) · [Raw samples and output bytes](analysis/compare.json) · [Complete serial/build/flash logs](logs/) · [Combined production diff](combined-pool.diff) · [Worktree provenance](workspace.log) · [Toolchain](toolchain.txt) · [Final audit](provenance/final-verification.txt)
