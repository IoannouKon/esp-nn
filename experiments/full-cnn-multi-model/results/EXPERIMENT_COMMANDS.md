# Experiment commands and local adaptations

The benchmark used the frozen manifest in the kit and the pinned detached worktree script. The four local TFLite Micro checkouts were cloned from the existing local Git object store and checked out at the same upstream revision. ESP-IDF was sourced from ~/esp_s3/esp-idf/export.sh.

From a fresh copy of the kit with an empty results directory, activate a Python 3.10 environment containing scripts/requirements-host.txt. Set ESP_NN_REPO and WORKSPACE to absolute paths.

```bash
set -e
mkdir -p results
sha256sum PRETRAINED_MODELS.json > results/pretrained-url-manifest.sha256
python scripts/download_pretrained.py --all --prepare-input
python scripts/download_pretrained.py --all --optional --prepare-input
bash scripts/prepare_mnist.sh "$ESP_NN_REPO"
python scripts/inspect_models.py
bash scripts/prepare_benchmark_workspace.sh "$ESP_NN_REPO" "$WORKSPACE"
source ~/esp_s3/esp-idf/export.sh
for model in mlperf_cifar10_resnet8 mlperf_vww_mobilenet tflm_person_detection mlperf_kws_dscnn; do
    bash scripts/run_one_model.sh "$WORKSPACE" "$model" /dev/ttyACM0
done
bash scripts/run_remaining.sh "$WORKSPACE" /dev/ttyACM0
for variant in opt2 mean; do
    python integration/enable_bridge.py "$WORKSPACE/$variant/app"
    bash integration/run_diagnostic.sh "$WORKSPACE" both "$variant" probe /dev/ttyACM0
    cp app/main/{main.cc,CMakeLists.txt} "$WORKSPACE/$variant/app/main/"
done
python scripts/desktop_reference.py
python scripts/compare_cnn.py results/logs --out results/analysis/compare
python scripts/write_report.py
python tests/test_metrics.py
```

The downloaded graph bytes and seed 20261121 are unchanged across variants. Fixed input shape comes from the upstream FlatBuffer schema. This allows the exact Person Detection model to reach the embedded runtime despite desktop TFLite rejecting its legacy affine bias metadata. Graph preflight records that desktop error separately.

The runner restores the same input before every Invoke because TFLite Micro can reuse its storage. The idle-task yield and serial printing stay outside the timed region. One initial ResNet8 capture had idle watchdog reports and a later monitor attachment missed the boot fingerprint. Those captures are preserved in attempts/ and excluded. The final monitor waits for the completed console banner, resets, requires a boot fingerprint, and saves the entire capture. The host parser checks the boot fingerprint against the built ELF and the emitted FNV-1a checksum against the complete output bytes.

The targeted custom CNNs use two deterministic training epochs on 20,000 CIFAR-10 training samples, fixed batch-one export and seeded full-integer calibration. The Keras archive used on this workstation has SHA-256 6d958be074577803d12ecdefd02955f39262c83c16fe9348329d7fe0b5c001ce. Training uses the same architecture definitions supplied in the kit and freezes the resulting bytes before firmware builds.

The supplied comparison script was extended to retain raw measurements, boot fingerprints, exact verified flash image sizes, memory usage and untimed dispatch evidence. Its smoke test verifies byte parity and rejects corrupt captures. The separate TensorFlow Lite desktop check uses the `BUILTIN_REF` operator resolver and the same frozen inputs.

The first optional ResNet6 boot completed at about 3.47 seconds per Invoke and emitted idle-watchdog reports. Its capture is archived under attempts/resnet6-watchdog and excluded. The complete optional model sweep runs a 20,000 ms idle-task watchdog threshold for every ResNet6 build, configured at startup before any timing. The SDK configuration files are identical across every captured build. ESP-IDF reported `v5.5.1-dirty`. The pre-existing changes were two example sources and an untracked ESP-WHO directory. The inference builds do not use those paths. See [IDF revision and status](idf-revision.txt).
