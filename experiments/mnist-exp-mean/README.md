# Frozen MNIST EXP-MEAN follow-up

[Full results and raw serial logs](results/MNIST_EXP_MEAN_RESULTS.md)

This experiment reuses the [original frozen MNIST app, model and input](../full-cnn-opt2/cnn_opt2/) from the Opt2 study. The commit contains the run scripts, all timing samples and output bytes, the exact SDK configuration, and selected compiler commands and symbol evidence. The physical board is required only to collect new measurements.

## Analyze the recorded run

Run from this directory.

```bash
python3 analyze.py
python3 write_report.py
```

## Repeat on the ESP32-S3-EYE

Use a scratch directory with a new results directory. Copy the scripts and the original SDK config and frozen hashes. Export the historical app and pinned runtime from local Git clones. Set WORKSPACE, ESP_NN_REPO and TFLM_REPO to absolute paths. The capture script uses /dev/ttyACM0 and the run script sources the historical ESP-IDF v5.5.1 installation under ~/esp_s3/esp-idf.

```bash
mkdir -p "$WORKSPACE"/{cnn_opt2,esp-tflite-micro,results}
cp analyze.py capture.py run.sh write_report.py "$WORKSPACE/"
cp results/{original.sdkconfig,model-input.sha256,graph.json} "$WORKSPACE/results/"
git -C "$ESP_NN_REPO" archive edb003c6770491abb74766835f4c803b9d4f5a20:experiments/full-cnn-opt2/cnn_opt2 |
    tar -x -C "$WORKSPACE/cnn_opt2"
git -C "$TFLM_REPO" archive df8722334a80ceabc609c1e72968f417cd9437f1 |
    tar -x -C "$WORKSPACE/esp-tflite-micro"
sed -i '/^    version: ">=1.4.2"/a\    override_path: "../espressif__esp-nn"' "$WORKSPACE/esp-tflite-micro/idf_component.yml"
git -C "$ESP_NN_REPO" worktree add --detach "$WORKSPACE/espressif__esp-nn" ace42ac7721119cd543fc40ffe719e601fa8f20f
cp "$WORKSPACE/results/original.sdkconfig" "$WORKSPACE/cnn_opt2/sdkconfig"
(cd "$WORKSPACE/cnn_opt2" && sha256sum -c ../results/model-input.sha256)
bash "$WORKSPACE/run.sh"
python3 "$WORKSPACE/analyze.py"
python3 "$WORKSPACE/write_report.py"
```
