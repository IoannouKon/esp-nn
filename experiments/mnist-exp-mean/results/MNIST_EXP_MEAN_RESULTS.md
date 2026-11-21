# Frozen INT8 MNIST CNN – EXP-MEAN comparison

The original full-CNN runner ran unchanged on the ESP32-S3-EYE at 240 MHz over USB Serial/JTAG on /dev/ttyACM0. Each timed build recorded 20 complete Invoke calls on each of two boots, after three warm-ups on each boot. The median uses all 40 timings per build.

| Firmware | Median (ms) | Speedup vs stock | Time reduction | Boot medians (µs) | All samples (µs) |
|---|---:|---:|---:|---|---|
| Stock ESP-NN v1.5.0 | 2.9110 | 1.0000× | +0.000% | 2911 / 2911 | 2911–2926 |
| Opt1 + Opt2 | 2.6610 | 1.0939× | +8.588% | 2661 / 2661 | 2661–2678 |
| EXP-MEAN | 2.9110 | 1.0000× | +0.000% | 2911 / 2911 | 2911–2926 |

## Historical comparison

| Implementation | Previous median | Current median | Change (µs) |
|---|---:|---:|---:|
| Stock ESP-NN v1.5.0 | 2.910 ms | 2.9110 ms | +1 |
| Opt1 + Opt2 | 2.660 ms | 2.6610 ms | +1 |

## Correctness and dispatch

All 120 timed inferences returned the original ten INT8 logits, with zero mismatched elements. The predicted digit was 7.

The original untimed probe logged 14 calls to the Opt2 sliding-row assembly for each of the 3×3 and 5×5 max-pool layers. The timed ELFs contained no dispatch wrappers. The stock and EXP-MEAN ELFs linked the stock ESP32-S3 max-pool entry point.

The frozen FlatBuffer contains two Conv2D layers, two MaxPool layers, Reshape and FullyConnected. The app registers only those four operator types. The EXP-MEAN timed ELF contains neither a linked TFLite Micro MEAN registration nor a linked ESP-NN global-mean or QACC function. EXP-MEAN executed zero times. Its timing is a negative control and the difference is not attributable to the mean optimization.

## Reproduction evidence

- ESP-TFLite Micro v1.4.3 at df8722334a80ceabc609c1e72968f417cd9437f1.
- ESP-IDF v5.5.1 at fcae32885b0296b32044cb99ecbdc50d98dddb83, Xtensa GCC 14.2.0.
- Single core, 240 MHz, 8 MiB octal PSRAM at 80 MHz, 64 KiB data cache and 16 KiB instruction cache.
- The exact original SDK config and frozen model/input were reused. The aligned 96 KiB PSRAM arena used 28,396 bytes on every captured boot.
- SDK config SHA-256 5ea49eaaf2fbf07731afeafef6fa25a6c78fc59e18b184b92d0c14d4c391b2af.
- Stock ESP-NN v1.5.0 at ace42ac7721119cd543fc40ffe719e601fa8f20f. [stock raw serial log](stock.log)
- Opt1 + Opt2 at edb003c6770491abb74766835f4c803b9d4f5a20. [opt2 raw serial log](opt2.log)
- EXP-MEAN at 4bfa49c64a932f700688c2007a01d8ea1fa102ac. [exp-mean raw serial log](exp-mean.log)

[Complete Opt2 diagnostic log](opt2-probe.log) · [Graph operator audit](graph.json) · [Every timing and output tensor](comparison.json) · [Original SDK config](original.sdkconfig) · [Frozen model/input hashes](model-input.sha256)
