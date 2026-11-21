# Codex Agent Task — Multi-CNN ESP-NN A/B/C/D experiment (ESP32-S3-EYE)

You have physical serial access to an ESP32-S3-EYE at 240 MHz with 8 MiB octal PSRAM. **Do the actual experiments**. This kit contains benchmark code and acquisition/generation steps, not precomputed speedup claims. Read README_START_HERE.md and docs/MODEL_MATRIX.md fully.

## Objective

Test whether two independent ESP-NN optimizations speed up **complete INT8 CNN inference** across diverse models, not just synthetic operator cases. Test four firmware variants built from the same model, operator integration, toolchain, IDF config, and input:

| Label | Revision | Meaning |
|---|---|---|
| Stock | `ace42ac7721119cd543fc40ffe719e601fa8f20f` | ESP-NN v1.5.0 |
| Opt2 | `edb003c6770491abb74766835f4c803b9d4f5a20` | Opt1+Opt2 max pooling, not Opt2 alone |
| EXP-MEAN | `4bfa49c64a932f700688c2007a01d8ea1fa102ac` | 16-lane QACC global mean |
| Combined | detached from EXP-MEAN with exact Opt2 production pooling diff applied locally | Both, experimental |

Repository: `IoannouKon/esp-nn`. Protect original branches, never force-push, rebase, or edit their worktrees. Use `scripts/prepare_worktrees.sh` to create detached copies. Verify clean stock and source differences; combined branch must include ONLY intended mean and max pool production code differences. Use Git diff, source hashes and linked symbol inspection.

## Critical technical discovery — do not overlook

Current Espressif ESP-TFLite Micro **calls ESP-NN for MaxPool** through `tensorflow/lite/micro/kernels/esp_nn/pooling.cc` (when ESP_NN enabled and channels % 4 == 0). However its builtin INT8 **MEAN** (`reduce.cc`, `reduce_common.cc`) calls a **TFLM reference reduce kernel**, not `esp_nn_mean_nhwc_s8()`. Therefore naïvely using `resolver.AddMean()` CANNOT exercise EXP-MEAN. Merely putting EXP-MEAN source in the ELF does not prove it ran. A claim of global-mean speedup based on the bundled `app/main/main.cc` alone is INVALID.

**Required mean-integration task before EXP-MEAN model claims:** Implement a separate, documented, guarded TFLM MEAN registration/adapter in the experimental app (and identically in all four builds). Preserve the builtin MEAN implementation for unsupported cases. It must select ESP-NN only for a strictly validated 4D NHWC int8 global reduction over spatial axes 1 and 2; check batch, keep_dims, quantization, tensor shapes, rounding/multiplier interpretation, pointer alignment, overlapping tensors, fallback and shape constraints. Compare against the original built-in TFLM MEAN with exact INT8 output tensor equality on realistic tensors and edge cases *before* performance testing. Do not assume ESP-NN's multiplier has the same meaning as the TFLM multiplier: derive the scale mapping from implementation and validate quantized rounding. For the stock build, the same adapter must call stock `esp_nn_mean`; for mean/combined builds it calls EXP-MEAN. Do not just compare optimized version to itself. No debugging wrappers/reference double-eval during timed Invoke. If you cannot prove strict correctness and actual dispatch, mark EXP-MEAN model results **INCONCLUSIVE** and complete honest Opt2 tests. Never hack model topology, quantization, rounding or reference code to manufacture agreement. Record integration code separately as research-only and call out that model-level gains depend on the new runtime adapter.

## Models to attempt

**Tier A: mandatory repeatable sources** (subject to successful build, memory and Invoke). First run the exact frozen MNIST model `mnist_fixed` fetched from prior Git commit with `scripts/prepare_mnist.sh`. Use `scripts/generate_models.py` to train, INT8-calibrate and freeze seven additional CIFAR-10 architectures: `max3`, `max5`, `mean_only`, `both`, `depthwise_both`, `avg_control`, `neutral_control`. They are distinct **custom CNN models**, not established SOTA architectures. Their 1-epoch/default limited training is strictly for functional inference testing. Document training accuracy honestly.

**Tier B: pretrained external architectures to attempt next if feasible:** Espressif Person Detection (real pretrained negative control), MobileNetV2 INT8, MobileNetV3-Small INT8, EfficientNet-**Lite0** INT8. Locate public reproducible actual `.tflite` INT8 files and their preprocessing. Record source URL, license, SHA, operator versions, actual tensor sizes, memory budget and quantization. Test on ESP32-S3-EYE only if TensorFlow Lite Micro operator resolution and memory allow it; report explicit SKIP with evidence otherwise. Do NOT substitute EfficientNetB0 while calling it Lite0; do not invent YOLO11n or hidden Espressif test models. Do not train random-initialized MobileNet and describe it as pretrained. A physically infeasible architecture is a legitimate skip, not a failed experiment.

## Model integrity gates

- Export each `.tflite` and a **fixed** quantized `input.bin` once; freeze them before any builds. Record model and input SHA256 in a model manifest. All four builds must embed bytes with identical hashes.
- Host preflight `scripts/inspect_models.py`: schema, INT8 I/O, input size, operator list, max pool filter/stride/padding and channels, MEAN axes/shape, host output, hashes.
- Resolver only registers implemented TFLM ops. If missing, audit/extend it for ALL four versions in identical app code. No silent fallback to different runtime (ESP-DL is not ESP-NN).
- Baseline and three candidates must use the **same model**, input, feature extractor and output comparison, including output dimensions and tensor memory placement. Compare **all output bytes**. If model output isn't single INT8 tensor, extend runner appropriately and retest all builds.
- Measure `MicroInterpreter::Invoke()` only, excluding model loading, preprocessing, camera I/O and initialization. Document whether app uses 2 MiB PSRAM arena and exact used memory. For large models, raise arena uniformly across ALL four builds after logging failure, and fail when board cannot fit. Do not reduce model resolution unnoticed.
- For max pool: instrument the actual C/assembly dispatch ONCE per model in a diagnostic, un-timed build; prove `esp_nn_max_pool_s8_esp32s3_sliding_row_asm` executes for intended 3×3 or 5×5 stride1 SAME shapes; report Opt1 fallback separately. Remove probes from timed builds.
- For mean: instrument genuine ESP-NN global mean invocation and classify QACC vs scalar fallback on the actual tensors. Ensure reference TFLM MEAN is not used for measured mean cases. Remove instrumentation from timed runs.
- Run official 580 unit tests at least once for both optimized branches (or link the previously verified results and state tests not rerun); compare test coverage explicitly, do not assert tests were rerun when they weren't.

## Benchmark protocol

- Board: ESP32-S3-EYE 240MHz, ESP-IDF v5.5.1 if compatible, 8MB octal PSRAM, 64KB D cache, one core. Use same toolchain and configuration across variants. Target ESP-TFLite Micro component v1.4.3 as in prior successful MNIST app; pin exact resolved commit and dependency lock. Do not accidentally link the component-registry stock ESP-NN into every firmware; inspect linkage and compile commands.
- Warmup 5 Invoke calls. Time **at least 30 independent complete invokes per firmware boot** (fixed frozen image is okay but clarify these are repeated executions of one input, not distinct image accuracy samples).
- Two complete boots per model and firmware, interleaved Stock → Opt2 → MEAN → Combined → Combined → MEAN → Opt2 → Stock. Logs from fresh flashed firmware. Capture exact model/input hashes and configs. Use median per boot and median across boots; include individual measurements and range.
- For stronger conclusions, after first pass choose at least 5–10 different frozen inputs for an additional correctness sweep on models that win. Inputs need not all be timed, but outputs must match across builds and host reference when semantics match.
- Limit **one benchmark capture** to <=20 minutes (excluding builds/flashing/training). `scripts/capture_serial.py` times out at 1200 s. If a huge model requires longer, skip or report with original dimensions.
- Record output tensors and hash each run, check stable within boot and exact equality across four firmware builds. Prefer report per-operator wall-time breakdown only if instrumentation removed during final timed runs.
- `scripts/run_model_sweep.sh` is optional automation once all copies are installed and app is built for the four worktrees. Inspect its paths, dependencies and flash commands first; do not execute blindly over an already modified worktree.

## Performance and attribution

Compute `speedup = stock_median_us / candidate_median_us`, `time_reduction = 100*(1-candidate/stock)`; WIN >1% faster, LOSS >1% slower, NEUTRAL otherwise. Report exact values, observed spread and any overlapping ranges. At least 30*2 timings per firmware per model. Two boots are not a confidence interval.

For EVERY model and firmware, report: name, origin, accuracy if genuinely measured, input/output shape, INT8 type, operator list, number of MEAN/MAX_POOL ops, which optimized symbols ACTUALLY EXECUTED, model/input SHA, fitted/not fitted, arena bytes, cold-start or warm-cache notes, per-boot medians, all-run median, speedup, cycle savings, exact output equality, verdict, code/heap/stack deltas if possible.

Very important: when normal TFLM MEAN is used, EXP-MEAN and combined results **must not** be attributed to QACC. A model with `MEAN` in its op table is NOT sufficient. If no mean bridge is completed and validated, report only Opt2 model gains; place EXP-MEAN in a separately clearly marked blocked/unmeasured section.

Do not cherry-pick models or hide losses; include skipped/not fitting models. Compare the combined configuration to each individual config and stock, but never assume kernel speedups add linearly. Keep the MNIST proof-of-concept result as historical reference only, not part of new measurements unless re-run.

## Deliverables

Place under `results/`:

- `CNN_RESULTS.md`: all attempted models, validated outcomes, failures and quantitative conclusions; classify **stock, Opt2, EXP-MEAN, combined** clearly.
- `comparison.csv`, `comparison.json`: all individual models and full raw timings (machine-readable).
- `logs/<model>/<version>-1.log` and `-2.log` per successful model/firmware; build/flash logs, skipped errors and diagnostic dispatch confirmations; never delete failures.
- `manifest.json`: source URLs, license, shape, operator registration, model/input hash and training accuracy.
- `build_provenance.md`: exact Git hashes for esp-nn, esp-tflite-micro, ESP-IDF, Python/TensorFlow, compiler commands and SDK configs, SHA matched across versions, dependency lock; source diff and binary text/data/bss measurements.
- If mean integration needed: `mean_bridge_patch/` with precise integration source, matched reference tests and clear explanation of quantization differences. Mark non-upstream runtime changes explicitly.
- One concise final verdict: **How many reproducible real CNNs improve? How much? Are differences attributable to Opt2, EXP-MEAN, or neither? What fails or regresses?**

Do not push, modify user branches, create PRs, publish claims, or change optimized production kernel code without explicit authorization. Return truthful measured evidence; INCONCLUSIVE or SKIPPED is preferable to false numbers.
