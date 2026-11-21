# ESP32-S3-EYE — reproducible FULL-CNN benchmark kit

**Goal:** Compare stock ESP-NN v1.5.0, Opt1+Opt2, EXP-MEAN, and their combination on the **exact same complete INT8 neural networks**, with microseconds, CPU cycles, and byte-for-byte output parity. The kit comes with acquisition scripts for **7 pretrained official reference models**, plus the previously benchmarked MNIST classifier and 7 reproducible custom CIFAR-10 architectures. Pretrained model weights must be downloaded from pinned upstream URLs by the agent host; models are not bundled due to download access and size. **Only historical MNIST board results exist.**

## Recommended priority

1. MLPerf Tiny CIFAR-10 ResNet8 — independent external image classification CNN.
2. MLPerf Tiny VWW MobileNetV1 — established real CNN at 96×96.
3. Official TFLM Person Detection — second MobileNet-based real workload.
4. MLPerf Tiny KWS DS-CNN — additional depthwise-CNN architecture over speech features.
5. Existing frozen MNIST CNN — known Opt2-positive reference.
6. Custom CIFAR-10 `max3`, `max5`, `mean_only`, `both` — targeted operator coverage (trained in preparation stage).
7. Optional larger ResNet / MobileNet models when memory/operator support permits.

## Fast start — on a Linux machine with ESP-IDF and internet

```bash
unzip ESP_NN_FULL_CNN_BENCHMARKS.zip
cd ESP_NN_FULL_CNN_BENCHMARKS
python3.10 -m venv .venv
source .venv/bin/activate
python -m pip install -r scripts/requirements-host.txt
# Download the four core PRETRAINED models, check source checksums/size, generate fixed INT8 inputs:
python scripts/download_pretrained.py --all --prepare-input
# Reuse the EXACT frozen MNIST CNN from our earlier board experiment:
bash scripts/prepare_mnist.sh /path/to/IoannouKon-esp-nn
# Train extra task-specific CIFAR CNNs ONLY when desired (separate from pretrained set):
python scripts/generate_models.py --only max3 max5 mean_only both --epochs 2 --train-samples 20000
# Validate actual TFLite operator lists, INT8 I/O, host output and SHA256:
python scripts/inspect_models.py
# Four detached worktrees + pinned local ESP-TFLite Micro and ESP-NN dependencies:
bash scripts/prepare_benchmark_workspace.sh /path/to/IoannouKon-esp-nn /path/to/empty-new-workspace
# Use your preinstalled ESP-IDF v5.5.1:
source /path/to/esp-idf/export.sh
# Physically runs all FOUR firmware versions, 30 inferences × 2 boots each:
bash scripts/run_one_model.sh /path/to/empty-new-workspace mlperf_cifar10_resnet8 /dev/ttyACM0
```

`--all` defaults to four core models. Add `--optional` for the three large references; or use `--models mlperf_vww_mobilenet ...` to choose explicitly. **The full experiment requires a board and may fail for a model that the pinned TFLM does not support or cannot fit in ESP32-S3 RAM. The agent must record SKIP and reason, never silently change the model.**

## Hardware/runtime

- ESP32-S3-EYE, 240 MHz, 8 MiB PSRAM. ESP-IDF v5.5.1 and ESP-TFLite Micro v1.4.3 pinned `df8722334a80ceabc609c1e72968f417cd9437f1`.
- Frozen INT8 model and input files remain byte-identical for all builds. Input is fixed deterministic raw INT8, **not** a dataset accuracy sample. For pretrained models, no claim of accuracy is made.
- A complete `MicroInterpreter::Invoke()` is timed with `esp_timer_get_time()` (µs) AND `esp_cpu_get_cycle_count()` (cycle counter). **Same-core cycle deltas can contain scheduling/interrupt overhead**; compare both and record the context.
- Five untimed warmups; 30 timed invocations per boot × 2 boots per firmware. `run_one_model.sh` automatically flashes and captures a clean reset after the monitor attaches.
- Complete output hex is preserved and compared across Stock, Opt2, MEAN, and Combined. A mismatch fails the analysis. Zero evidence is not labelled PASS.
- Results: `results/logs/<model>/`, `results/analysis/compare.csv`, `results/analysis/compare.json`.

## Important limitations

**Opt2**: normal optimized ESP-TFLM MaxPool path does call ESP-NN, but it only hits Opt2 sliding SIMD on eligible geometry/alignment. Verify actual call with an untimed symbol/dispatch probe before attributing wins. Most MLPerf reference networks use convolutions, depthwise convolutions, and average pooling; many may **never call Opt2**, making them useful NEGATIVE CONTROLS.

**EXP-MEAN**: TFLM built-in INT8 MEAN uses its own reference reduction. Simply compiling the QACC branch into the app does not activate it. You need a separate, proven equivalent runtime adapter for actual model-level EXP-MEAN gains. This kit does NOT fabricate a working MEAN adapter. Until the agent implements a verified exact-byte MEAN bridge and proves dispatch, results for mean/combined are neutral *controls* only; QACC improvement is **UNMEASURED**. See `docs/MEAN_BRIDGE_REQUIREMENTS.md`.

**No board validation of these newly selected pretrained models has been performed in this environment.** The agent needs to compile and run them physically. This bundle includes source code and reproducible model download commands, NOT claimed hardware benchmark outcomes.

## Test the included host tooling

```bash
python -m compileall -q scripts
python tests/test_metrics.py
```

Read `docs/MODEL_SELECTION.md` and `AGENT_PROMPT.md` before running large sweeps.
