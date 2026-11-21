# Why a verified TFLM→ESP-NN MEAN bridge is necessary

On the pinned `espressif/esp-tflite-micro` runtime, `resolver.AddMean()` dispatches into TFLM `tensorflow/lite/micro/kernels/reduce.cc` / `reduce_common.cc`, which execute quantized reference reductions, **not** `esp_nn_mean_nhwc_s8`.

**Implication:** even if `mean_only`, `both`, or an upstream pretrained model includes a `MEAN` operator, the EXP-MEAN branch will not execute QACC from this runner. Link presence and an op-table entry are insufficient. A model-level EXP-MEAN speedup claim is prohibited until bridge + correctness gates pass.

Implementation work for an agent who will validate on the board:

1. Read **actual** `esp_nn_mean_nhwc_s8` signature and `esp_nn_mean_s8_esp32s3.c`, TFLM `EvalMeanHelper` and reference quantized Mean code. Do not assume quantization multiplier/shift conventions match.
2. Create a **separate experimental** custom `TFLMRegistration` for `MEAN`, shared **byte-identically** among Stock, Opt2, Mean, Combined builds. The wrapper should guard 4D NHWC batch1, reduction axes `[1,2]`, correct `keep_dims`, 8-bit I/O, supported areas, shape/strides/alignment, no aliasing, zero points and true quantized scale. Use stock `esp_nn_mean` for Stock and Opt2, candidate `esp_nn_mean` for Mean and Combined. Unsupported cases must fall back to the original TFLM MEAN without changing results.
3. Validate output against original stock TFLM MEAN for thousands of random + adversarial inputs and quantization combinations; compare complete output tensors **bit-for-bit**. If standard ESP-NN mean semantics differ, document the difference and **do not benchmark an inequivalent model**.
4. Log actual QACC dispatch in an untimed diagnostic build (candidate assembly invocation and SIMD eligibility). Avoid including probes in timed builds.
5. Only then report genuine full-CNN EXP-MEAN and combined results. This kit deliberately does not provide a speculative adapter claimed to work.

A practical alternative is a **separate direct ESP-NN mean microbenchmark**, but it is NOT a full-CNN benchmark. It must remain labelled accordingly.
