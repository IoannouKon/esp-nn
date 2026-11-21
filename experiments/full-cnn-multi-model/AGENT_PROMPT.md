# Codex agent assignment — full-CNN ESP-NN benchmarks with real pretrained models

You have access to an actual ESP32-S3-EYE and a Linux machine with ESP-IDF. Execute this package, produce a **reproducible, source-grounded experiment**, and return all evidence. Do not invent measured speeds or pretend external reference models executed when build/AllocateTensors failed.

1. Read `README_START_HERE.md`, `docs/MODEL_SELECTION.md` and `docs/MEAN_BRIDGE_REQUIREMENTS.md` completely.
2. Freeze the exact seven upstream source URLs in `PRETRAINED_MODELS.json` (4 core, 3 optional), download the four core pretrained TFLite binaries via `python scripts/download_pretrained.py --all --prepare-input`, audit graph ops via `python scripts/inspect_models.py`; use `--optional` when feasible. Download first on your agent machine (internet access), not via board. Never silently substitute another model.
3. Retrieve historical frozen model `mnist_fixed` via `bash scripts/prepare_mnist.sh /path/to/IoannouKon/esp-nn`. This was previously tested on hardware and is useful as a known positive control for Opt2. Only after core pretrained models run, create targeted CIFAR10 custom models `max3`, `max5`, `mean_only`, `both`, `depthwise_both` with `scripts/generate_models.py`. They require TensorFlow and training; mark them as custom, not pretrained.
4. Use the pinned 4-variant worktrees created by `scripts/prepare_benchmark_workspace.sh /path/to/repo /new/workspace`:
   Stock `ace42ac7721119cd543fc40ffe719e601fa8f20f`, Opt2 `edb003c6770491abb74766835f4c803b9d4f5a20`, Mean `4bfa49c64a932f700688c2007a01d8ea1fa102ac`, Combined (detached Mean + ONLY production pool patch from Opt2). The original Git branches are untouched; never push or force-update.
5. Use pinned ESP-TFLite Micro v1.4.3 commit `df8722334a80ceabc609c1e72968f417cd9437f1` and ESP-IDF v5.5.1 if available; verify `idf.py --version` and compile source paths. The local component manifests must resolve the ESP-NN worktree, NOT pull registry stock ESP-NN for every build. All sdkconfig, clock, caching, compiler, arena and input files must be identical across builds. CPU240MHz, 8MB PSRAM.
6. Run each fitting model using `bash scripts/run_one_model.sh /new/workspace MODEL_NAME /dev/ttyACM0`. 5 warmups, 30 complete `Interpreter.Invoke()` times and CPU cycles per boot, 2 boots per build, interleaved Stock/Opt2/Mean/Combined/Combined/Mean/Opt2/Stock. Limit each capture to 20min excluding builds/flashing. The script attaches ESP-IDF monitor then sends reset to avoid missing fast benchmarks, saves build/flash/full serial logs, checks local component provenance, rejects mismatched output bytes.
7. If a model does not allocate, uses unsupported op or exceeds memory, log failure with exact model SHA, stack/arena/data and explain SKIP. Do not downgrade resolution, modify graph or quietly swap a different model; if you change arena across all four builds, document and re-run all four.
8. Prove optimized execution separately: use untimed call instrumentation or linker wrapper for ESP-NN MaxPool/sliding assembly and MEAN. Models with no eligible operations are **negative controls**. Never attribute effects to a kernel that did not execute.
9. Special case **EXP-MEAN**: the builtin `AddMean()` in pinned TFLM DOES NOT call ESP-NN. The current kit intentionally provides no unverified custom MEAN integration. To benchmark full-CNN QACC you must implement a separate research-only guarded custom `MEAN` registration/adapter in the app, identical for all four builds, backed by exhaustive byte-for-byte equality to TFLM reference and actual QACC call proof. If not possible, label EXP-MEAN/Combined full-CNN results `CONTROL ONLY / NO QACC EXECUTION`; do not claim an EXP-MEAN CNN win. Retain all unmodified comparison results.
10. Provide `results/CNN_RESULTS.md` (model list, observed/attempted/skip, operator map, exact hashes, full output parity, inference us and cycles, speedup vs stock, memory, dispatch proof), `results/analysis/compare.csv`, `compare.json`, raw serial/build/flash logs, complete environment provenance and commands. Distinguish all operator-only benchmarks from actual complete CNN tests. At least three successfully run distinct real pretrained CNNs if the hardware/runtime permits; otherwise report hard evidence of each blocker. Do not cherry pick models or report model accuracy from deterministic random input.

Commands:

```bash
unzip ESP_NN_FULL_CNN_BENCHMARKS.zip
cd ESP_NN_FULL_CNN_BENCHMARKS
python3.10 -m venv .venv && source .venv/bin/activate
python -m pip install -r scripts/requirements-host.txt
python scripts/download_pretrained.py --all --prepare-input
bash scripts/prepare_mnist.sh /path/to/esp-nn
python scripts/inspect_models.py
bash scripts/prepare_benchmark_workspace.sh /path/to/esp-nn /new/workspace
source /path/to/esp-idf/export.sh
bash scripts/run_one_model.sh /new/workspace mlperf_cifar10_resnet8 /dev/ttyACM0
bash scripts/run_one_model.sh /new/workspace mlperf_vww_mobilenet /dev/ttyACM0
bash scripts/run_one_model.sh /new/workspace tflm_person_detection /dev/ttyACM0
bash scripts/run_one_model.sh /new/workspace mlperf_kws_dscnn /dev/ttyACM0
bash scripts/run_one_model.sh /new/workspace mnist_fixed /dev/ttyACM0
```

All instructions conditional on successful host preflight, build and physical run. Source ZIP is not proof of board validity. Deliver raw data even if optimization produces no advantage. No Git pushes without permission.
