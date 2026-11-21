# Build provenance and replay

## Pinned source and board

| Component | Exact source |
|---|---|
| Stock ESP-NN v1.5.0 | ace42ac7721119cd543fc40ffe719e601fa8f20f |
| Opt1+Opt2 | edb003c6770491abb74766835f4c803b9d4f5a20 |
| EXP-MEAN | 4bfa49c64a932f700688c2007a01d8ea1fa102ac |
| Combined | EXP-MEAN plus the two Opt2 pooling source files. The working diff is byte-for-byte identical to the stock-to-Opt2 diff for those files. |
| ESP-TFLite Micro v1.4.3 | df8722334a80ceabc609c1e72968f417cd9437f1 |
| ESP-IDF v5.5.1-dirty | fcae32885b0296b32044cb99ecbdc50d98dddb83. The installed tree has pre-existing edits in examples and an untracked esp-who checkout. |
| Compiler | Espressif Xtensa GCC 14.2.0, crosstool-NG esp-14.2.0_20241119 |
| Host model generation | TensorFlow/Keras 2.15.1, Python 3.10, NumPy, Pillow 10.4.0 for the external model image resize |
| Hardware | ESP32-S3-EYE, ESP32-S3 v0.2, one core, actual 240 MHz per boot log, 8 MiB octal PSRAM at 80 MHz, 8 MiB flash at 80 MHz, 64 KiB 8-way data cache and 64-byte cache lines |
| Serial | /dev/ttyACM0, USB Serial/JTAG at the monitor's 115200 baud; hardware symlink in build/serial-device.txt |
| Build | ESP-IDF minimal component graph and performance optimization, ESP-TFLM ESP-NN enabled, NN_OPTIMIZED, ordinary flash-mapped model bytes, aligned PSRAM arena of 2 MiB for the core suite and EfficientNet-Lite0, or 4 MiB for both MobileNets |

The four detached ESP-NN trees live under multi-cnn-run. The exact Combined patch has SHA256 ef9e490bd6153d91cb38adb4cfb5d0cecc40fe67e19cc4cd952654f753f4a15f. The original branch refs remain in their originating repository. ESP-IDF component-manager override manifests select an exact archived ESP-TFLM revision and a relative path to each local ESP-NN tree. See per-firmware dependency locks and compile command extracts. The manifests preserve ESP-TFLM's original requirements. The app's TFLM binding, diagnostic and shape handlers live in the experiment package.

[Combined pooling patch](build/combined-pooling.diff) · [Original branch diff](build/stock-to-opt2-pooling.diff) · [Detached revisions](build/revisions-before.txt) · [IDF checkout status](build/esp-idf-git.txt)

## Method

Core models were placed in one firmware bundle in manifest order beginning with frozen MNIST. Large pretrained models use separate flash bundles because of flash capacity. All four variants in a group embed the same frozen inputs and models. The analysis uses two fresh reset captures per variant in the order stock, Opt1+Opt2, EXP-MEAN, Combined, Combined, EXP-MEAN, Opt1+Opt2, stock. Each board capture has a hard 1,200 second read bound independent of flashing and compilation. Separate diagnostic firmware records symbol calls; timed firmware has no diagnostic wrapper symbols. Flash writes are verified in the preserved flash logs.

For every timed inference the runner restores the fixed input before opening the timer because TFLM's greedy arena planner can reuse the input region after its final consumer. One preliminary stock boot with the kit's once-per-model input copy exposed unstable outputs and was rejected. After five warm-ups the timer brackets exactly Invoke for 30 samples. The runner prints timing and outputs after the timed loop. The large external models get a scheduler tick between inferences to keep the task watchdog serviced, outside the measured region. Each small vision model also runs six frozen non-timed inputs. Output bytes are checked within a boot, across both boots, and across the four variants.

Three Keras CNN exports with MEAN produced Dense reshapes whose intermediate dynamic dimension was represented as 1 in the FlatBuffer. The experiment resolves the actual fixed batch-one shape before the final build. Exactly one shape vector per affected model changes from [1,1] to [1,32]. The original exports, exact changed offsets, before/after SHA256 and seven-input exact desktop reference checks are preserved. The FlatBuffer operators, training weights, quantization, and input/output tensors stay the same. The common app implements the narrow INT32 GATHER and REDUCE_PROD shape operations those graphs require.

[Rejected stock boot](logs/suite_core/stock-1-rejected-input-reuse.log) · [Shape normalization evidence](static_tensor_shapes.json) · [MEAN bridge](mean_bridge_patch/README.md)

## Historical kernel correctness

The official test_app was not rerun as part of these CNN captures. The previously recorded Opt2 and EXP-MEAN runs each passed 580 tests with zero failures or skips. Opt2's tested commit 255d96b193eef37f75ca4e3cab950e1301ca6f0e has the same production source as the CNN-pinned edb003c6770491abb74766835f4c803b9d4f5a20. The old tests cover the isolated kernels and alignment, while the new diagnostics compare graph dispatch and MEAN semantics against TFLite Micro and the timed app compares whole outputs.

[Opt2 official test log](logs/historical/opt2-official-test_app.log) · [EXP-MEAN official test log](logs/historical/exp-mean-official-test_app.log)

## Reproduction

Use the frozen files in ../models and the scripts in ../scripts. For retraining, use the kit generator's default one epoch, 12,000 training examples, fixed seed 1729 and full-integer quantization with 128 calibration images. The canonical CIFAR-10 tarball SHA256 is 6d958be074577803d12ecdefd02955f39262c83c16fe9348329d7fe0b5c001ce; the mirror download matched the upstream Keras hash. The only serialization fix in the generator converts NumPy shape vectors to JSON-native integers. The app resolution workaround is then replayed by static_tensor_shapes.py after preparing the six validation inputs.

With ESP-IDF v5.5.1 active, and access to local clones of IoannouKon/esp-nn and espressif/esp-tflite-micro, use a scratch copy of this experiment, clear its existing results/logs directory, and set ESP_NN_REPO, ESP_TFLM_REPO and REPLAY_WORKSPACE to absolute paths. Run from the scratch copy:

```bash
bash scripts/prepare_worktrees.sh "$ESP_NN_REPO" "$REPLAY_WORKSPACE"
bash scripts/stage_runtime.sh "$ESP_TFLM_REPO" "$REPLAY_WORKSPACE"
bash scripts/build_matrix.sh "$REPLAY_WORKSPACE" core mnist_fixed max3 max5 mean_only both depthwise_both avg_control neutral_control person_detection --validation
idf.py -C "$REPLAY_WORKSPACE/combined/app" --ccache -B build-probe -DIDF_TARGET=esp32s3 -DCNN_DIAGNOSTIC=ON build
/usr/bin/python3 scripts/run_suite.py "$REPLAY_WORKSPACE/combined/app" build-probe results/logs/suite_core/combined-diagnostic.log
bash scripts/run_matrix.sh "$REPLAY_WORKSPACE" core
bash scripts/run_external.sh "$REPLAY_WORKSPACE" mobiles mobilenet_v2 mobilenet_v3_small
bash scripts/run_external.sh "$REPLAY_WORKSPACE" lite0 efficientnet_lite0
python scripts/analyze_suite.py
python scripts/verify_builds.py
python scripts/write_report.py
```

The same staged core app supplies the Combined diagnostic build. The external script validates its own dispatch before collecting timings. Use a new copy of the kit to preserve prior captures. Preserve the complete monitor output for each boot. The raw captures are authoritative; per-model files are subsections generated from them.

## External model fit and untimed fidelity check

The initial MobileNet diagnostic measured the allocator head requirements before rejecting the 2 MiB arena. The same two model files and input blobs were retried with a 4 MiB arena selected for all four timed builds. The core and EfficientNet-Lite0 firmware use the original 2 MiB capacity.

[2 MiB MobileNet attempt](logs/suite_mobiles/combined-diagnostic-2097152.log) · [4 MiB MobileNet dispatch check](logs/suite_mobiles/combined-diagnostic-4194304.log) · [EfficientNet-Lite0 dispatch check](logs/suite_lite0/combined-diagnostic.log)

The separate MobileNet fidelity diagnostic uses stock ESP-NN sources and the pinned ESP-TFLite Micro CMake diagnostic switch ESP_NN_OFF_PROBE. That switch compiles out ESP-NN calls in the TFLite Micro uses guarded by ESP_NN. This build runs one untimed Invoke on each identical MobileNet image and prints all output bytes. Its results are used only for fidelity diagnosis.

[Reference app diff](diagnostics/stock_tflm_reference.patch) · [Selected reference compile commands](diagnostics/reference_compile_commands.json)

The Git snapshot includes the frozen inputs, selected models, full serial logs, ELF fingerprints, section sizes and build metadata. The original experiment workspace also retains the generated firmware binaries and debug ELFs. Replaying the builds produces local binaries for the verifier.
