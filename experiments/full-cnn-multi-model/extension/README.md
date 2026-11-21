# Global Mean follow-up

This subdirectory extends the immutable 13-model benchmark in the parent directory. The original archive, models, trace files and analysis stay at their original paths. The updated 15-model report, added runs and profiling evidence live under [results](results/).

## Models and inputs

The two additional classifiers use 32×32 RGB CIFAR-10, two valid-padding 3×3 ReLU convolutions, spatial Global Mean with retained dimensions, and a ten-class dense head. The first convolution produces 30×30×16. The second uses stride 2 and 128 filters for CIFAR-Mean-Wide, and stride 1 and 32 filters for CIFAR-Mean-Large. The MEAN input tensors contain 25,088 INT8 values in both graphs, arranged as 14×14×128 and 28×28×32. The actual exported FlatBuffers and per-tensor quantization are audited in models/mean_graphs.json. The frozen depthwise_both graph uses 16×16×32. The other two historical QACC graphs use 8×8×32.

The training wrapper calls the original generator's training, calibration and fixed batch-one exporter. It uses Python 3.10.13, tensorflow-cpu 2.15.1 and NumPy 1.26.4. Each new model trains for two epochs on the same first 20,000 CIFAR-10 training examples with seed 1729 and the original 128-example calibration. The CIFAR archive SHA-256 was 6d958be074577803d12ecdefd02955f39262c83c16fe9348329d7fe0b5c001ce. The frozen timed input comes from test index 0. Each of the five QACC models also has 12 separate inputs covering constants, a checkerboard, seeded random inputs and CIFAR-10 test images. The correctness firmware checks the activation tensor and entire output bytes for each case, using the original dual TFLite Micro reference check, plus heap and arena boundary checks.

The first training log ends at an audit assertion for the assumed historical depthwise shape after both new models had trained and exported. The corrected audit reused those frozen models. Independent retraining produced byte-identical models, fixed inputs and extra fixtures. The labeled INT8 assessment uses flattened ten-class logits from the frozen exports.

## Replay

Run these commands from the parent benchmark package directory. Set ESP_NN_REPO to a local repository containing the three pinned commits and WORKSPACE to an absolute path. Source the same ESP-IDF release, v5.5.1 at fcae32885b0296b32044cb99ecbdc50d98dddb83. The original workspace script pins ESP-TFLite Micro to df8722334a80ceabc609c1e72968f417cd9437f1. The physical board was on /dev/ttyACM0. Run the hardware commands from a separate replay copy with no existing extension/results/full, profile or per-model diagnostics to preserve historical evidence.

```bash
sha256sum -c results/ARTIFACTS.sha256
# Optional deterministic regeneration on the host using the original TensorFlow environment.
TF_CPP_MIN_LOG_LEVEL=3 TF_NUM_INTRAOP_THREADS=3 TF_NUM_INTEROP_THREADS=1 \
TF_ENABLE_ONEDNN_OPTS=0 TF_DETERMINISTIC_OPS=1 \
    python extension/scripts/prepare_models.py --cifar-cache /path/to/keras-cache

bash scripts/prepare_benchmark_workspace.sh "$ESP_NN_REPO" "$WORKSPACE"
source /path/to/esp-idf/export.sh
bash extension/scripts/run_study.sh "$WORKSPACE" /dev/ttyACM0
python3 extension/scripts/analyze.py
# Run with matplotlib 3.8.2 and NumPy available.
python3 extension/scripts/report.py
```

The board driver uses the original runner and capture scripts for full and profiling measurements. Full timing uses the original app and original MEAN bridge. The profiling overlay measures the same ESP-NN operation with the same adapter and alternates a nested timer on and off inside one firmware image. The paired calls share memory placement and binary layout. The extra correctness overlay uses the original probe and reference code, with guards outside the logical arena. The phases are independent. To rerun a specific phase, append the phase name (correctness, full or profile) and a model ID to the driver command.

The original board run used a pre-existing detached workspace from the first experiment. It reused the same 240 MHz single-core and 8 MiB PSRAM board and the same 2 MiB arena. The orchestration check verifies checkout pins and the two-file Combined overlay before flashing. The pinned IDF checkout's status is recorded under results. SDK, compiled source paths, source hashes, flash identity, firmware image size and boot output remain with each capture.

## Data

- [Unchanged initial study](../results/CNN_RESULTS.md)
- [15-model report](results/CNN_RESULTS.md)
- [Full-model data](results/analysis/compare.csv)
- [Isolated MEAN data](results/analysis/mean_profile.csv)
- [Individual full samples](results/analysis/full_samples.csv) and [individual MEAN sample pairs](results/analysis/mean_profile_samples.csv)
- [All samples, correctness results and output bytes](results/analysis/compare.json)
- [Uninstrumented inference captures](results/full/)
- [Paired profiling captures](results/profile/)
- [Untimed correctness and dispatch runs](results/diagnostics/)
