# Full INT8 CNN inference with ESP-NN Opt2

## Model and training

This is a **custom MNIST CNN experiment** on the ESP32-S3-EYE. I checked publicly available models before using the fallback. The MLPerf Tiny CIFAR-10 reference uses average pooling, and I could not verify a published INT8 classifier with the required stride-1 SAME max-pool layers and reproducible ESP-TFLite Micro setup. I trained a compact digit classifier on the standard MNIST split. [MLPerf Tiny reference architecture](https://github.com/mlcommons/tiny/blob/master/benchmark/training/image_classification/keras_model.py) · [MNIST dataset](https://keras.io/2/api/datasets/mnist/)

| Layer | Configuration | Output NHWC or flat shape |
|---|---|---|
| Input | 28×28 grayscale MNIST | 1×28×28×1 |
| Conv2D + ReLU | 16 filters, 3×3, stride 2, SAME | 1×14×14×16 |
| MaxPool | 3×3, stride 1, SAME | 1×14×14×16 |
| Conv2D + ReLU | 32 filters, 3×3, stride 2, SAME | 1×7×7×32 |
| MaxPool | 5×5, stride 1, SAME | 1×7×7×32 |
| Flatten → Dense | Ten digit logits | 1×10 |

TensorFlow CPU 2.15.1 trained 20,490 parameters on all 60,000 training examples for four epochs with Adam (learning rate 0.001), batch size 128, sparse cross-entropy, and seed 1729. Pixels were normalized by 255. Post-training quantization used 256 seeded training images for calibration, TFLite integer-only built-ins, and INT8 inputs and outputs. Weights are INT8 and biases use INT32. Accuracy on all 10,000 held-out examples was **98.39% float** and **98.35% INT8** (9,835 correct). [Training source](cnn_opt2/train.py) · [Training metadata](cnn_opt2/training_result.json) · [Training log](results/cnn-opt2/training.log)

Both firmware builds use the same frozen [model](cnn_opt2/main/model.tflite) and [fixed INT8 input](cnn_opt2/main/input.bin). The input is MNIST test image 0, whose label is **7**. SHA-256 values are checked against the [frozen manifest](results/cnn-opt2/model-input.sha256).

## Hardware and software

- ESP32-S3-EYE on `/dev/ttyACM0` using USB Serial/JTAG, CPU at 240 MHz, 8 MiB octal PSRAM at 80 MHz. The build uses FreeRTOS uniprocessor mode, a 64 KiB D-cache, a 16 KiB I-cache and an aligned 96 KiB tensor arena allocated explicitly in PSRAM.
- ESP-IDF `v5.5.1-dirty` at `fcae32885b0296b32044cb99ecbdc50d98dddb83`. Its pre-existing tracked edits are in the blink and hello-world examples. Xtensa GCC 14.2.0, ESP-IDF performance build, optimized ESP-NN enabled. ESP-TFLite Micro `v1.4.3` at `df8722334a80ceabc609c1e72968f417cd9437f1`.
- Local ESP-NN dependency override links stock `v1.5.0` at `ace42ac7721119cd543fc40ffe719e601fa8f20f` or combined Opt2 at `255d96b193eef37f75ca4e3cab950e1301ca6f0e`. The shared application, generated SDK configuration and model/input files are the same for both timed builds. [SDK config](results/cnn-opt2/sdkconfig) · [Dependency lock](results/cnn-opt2/dependencies.lock)

## Opt2 dispatch verification

A single, untimed Opt2 invocation used link-time wrappers around `esp_nn_max_pool_s8_esp32s3` and `esp_nn_max_pool_s8_esp32s3_sliding_row_asm`. The wrapper forwarded the original arguments and recorded the actual addresses and row calls. Both layers used 16-byte-aligned, nonoverlapping input and output ranges.

| Pool tensor | Filter | Input address | Output address | Opt2 row calls |
|---|---|---|---|---:|
| 14×14×16 | 3×3, stride 1, SAME | `0x3c050900` | `0x3c055fe0` | 14 |
| 7×7×32 | 5×5, stride 1, SAME | `0x3c056c20` | `0x3c050f20` | 14 |

`PROBE_OPT2=OFF` excluded the wrapper source and link options from both timed builds. The linked stock image had the ESP32-S3 max-pool entry point. The linked Opt2 image also had the sliding-row function. [Diagnostic log](results/cnn-opt2/probe.log) · [Probe source](cnn_opt2/main/probe.cc) · [Stock linked symbols](results/cnn-opt2/stock-pool-symbols.txt) · [Opt2 linked symbols](results/cnn-opt2/opt2-pool-symbols.txt)

## Timing and exact output equality

**WIN.** The full median `Invoke()` fell from **2.910 ms to 2.660 ms**, saving **250 µs (8.59%)** for **1.094× speedup**.

| Measurement | Stock ESP-NN | Opt2 |
|---|---:|---:|
| CNN model and fixed input | Frozen INT8 MNIST CNN, test image 0 | Identical |
| Timed inferences | 40 | 40 |
| Full inference time, median | 2,910 µs | 2,660 µs |
| Range (max − min) | 2,909–2,924 µs (15 µs) | 2,659–2,677 µs (18 µs) |
| Median by boot | 2,910 / 2,910 µs | 2,660 / 2,660 µs |
| Speedup | 1.00× | 1.094× |
| Exact outputs | Reference | PASS |
| Opt2 executed | N/A | YES, both layers in the diagnostic invocation |
| Verdict | Baseline | WIN |

For each build I collected 20 measurements after three warm-up invocations on each of two boots. Only `MicroInterpreter::Invoke()` was timed, using `esp_timer_get_time()`. The program copies and prints the complete output outside the timed interval. Both timed builds allocated the arena at `0x3c050900` and reported 28,396 bytes used. Opt2’s slowest sample was 232 µs faster than stock’s fastest sample, exceeding the variation observed within either build.

All 80 timed invocations produced these ten INT8 logits, in digit order, and predicted class **7**.

```text
[-32, -4, 44, 14, -24, -25, -103, 98, -24, 30]
```

The 40 paired output tensors contained 400 compared elements, **zero mismatches**, and a maximum absolute difference of **0**. The vectors also matched the host TFLite output for this image. [Stock serial log](results/cnn-opt2/stock.log) · [Opt2 serial log](results/cnn-opt2/opt2.log) · [Machine-readable timings and all outputs](results/cnn-opt2/summary.json)

### Individual inference times (µs)

```text
stock boot 1  2924, 2910, 2914, 2909, 2910, 2914, 2910, 2909, 2910, 2915, 2909, 2910, 2914, 2910, 2910, 2914, 2910, 2909, 2910, 2915
stock boot 2  2924, 2910, 2914, 2909, 2910, 2914, 2910, 2909, 2910, 2915, 2909, 2910, 2914, 2910, 2910, 2914, 2910, 2909, 2910, 2915
opt2  boot 1  2677, 2660, 2665, 2660, 2659, 2660, 2664, 2659, 2660, 2659, 2665, 2660, 2659, 2665, 2659, 2660, 2660, 2664, 2660, 2659
opt2  boot 2  2677, 2660, 2665, 2660, 2659, 2660, 2664, 2660, 2660, 2659, 2665, 2660, 2659, 2665, 2659, 2660, 2660, 2664, 2660, 2659
```

## Reproduction and limits

1. Place ESP-TFLite Micro v1.4.3 at `esp-tflite-micro/` next to `cnn_opt2/`. In its root `idf_component.yml`, set `override_path: "../espressif__esp-nn"` under the `espressif/esp-nn` dependency. Create an ESP-NN worktree named `espressif__esp-nn/` next to `cnn_opt2/` and check out the exact revision for each run. The application and dependency override sources use those directory names. [Application source](cnn_opt2/main/main.cc) · [ESP-TFLite Micro v1.4.3](https://github.com/espressif/esp-tflite-micro/tree/v1.4.3)
2. Use the frozen model and input for the device comparison. To reproduce training separately, install [the pinned dependencies](cnn_opt2/requirements.txt) in a Python 3.10 virtual environment and run `python cnn_opt2/train.py`. The MNIST archive used here had SHA-256 `731c5ac602752760c8e48fbffcf8c3b850d9dc2a2aedcf2cc48468fc17b673d1`.
3. Activate ESP-IDF and enter `cnn_opt2/`. In a fresh build, run `idf.py --ccache -B build-cnn set-target esp32s3`. With Opt2 selected, build with `idf.py --ccache -B build-cnn -D PROBE_OPT2=ON build`, then run `idf.py --ccache -B build-cnn -p /dev/ttyACM0 flash monitor`. Save the serial output through `CNN_DONE` as `probe.log`.
4. For each timed revision build with `idf.py --ccache -B build-cnn -D PROBE_OPT2=OFF build`. Use the same flash/monitor command and capture both boots in the same log. After the first `CNN_DONE`, press `Ctrl+T`, then `Ctrl+R` to reset. Exit after the second `CNN_DONE` with `Ctrl+]`. Run `python3 cnn_opt2/analyze.py results/cnn-opt2` from this experiment directory to verify dispatch and compare timings and outputs.
5. With a different absolute workspace path, let Component Manager regenerate its lock so it records the two local component paths correctly.

These measurements cover one trained CNN, one fixed test image, and one board at one clock and memory configuration. Held-out accuracy was measured on the host. Board output equality was verified on the fixed image. The board remains flashed with the timed Opt2 build. The ESP-NN optimization commits and official kernel benchmark were left intact. [Official kernel benchmark](../../bench_app/README.md)
