# EXP-MEAN on ESP32-S3-EYE

## Hardware and software

- Physical ESP32-S3-EYE, ESP32-S3 QFN56 revision v0.2. USB Serial/JTAG at `/dev/ttyACM0`, monitor at 115200 baud. The boot log confirms 240 MHz, 8 MiB octal PSRAM at 80 MHz. The benchmark SDK config uses a 16 KiB 8-way I-cache with 32-byte lines and a 64 KiB 8-way D-cache with 64-byte lines.
- ESP-IDF `v5.5.1-dirty`, Git base `fcae32885b0296b32044cb99ecbdc50d98dddb83`. The pre-existing tracked edits are in the blink and hello-world examples. Xtensa GCC 14.2.0, toolchain `esp-14.2.0_20241119`. Both builds use the app's default optimized ESP-NN configuration, the same toolchain, and ccache. ESP-NN uses its repository-defined `-O2`.
- Stock was the clean, detached `v1.5.0` worktree at `ace42ac7721119cd543fc40ffe719e601fa8f20f`. Candidate was the same base in the separate `experiment/s3-global-mean-qacc` worktree plus the supplied patch, subsequently committed as `2f86cf16037d6e488702d717459ccf7762b423c3`. The patch applied cleanly and needed zero implementation corrections. The earlier max-pool branch remained at `edb003c6770491abb74766835f4c803b9d4f5a20`.
- Stock and candidate benchmark SDK configs are byte-identical. Both SHA-256 values are `a185c620162ebe86aab4721c9fe440f8680333e6b4b76c2af327f47c102f945b`. Git tree and blob IDs and a working-tree diff verify identical `bench_app`, `test_app`, test sources and ANSI mean reference. [Configs](sdkconfig-sha256.txt) · [Git and toolchain checks](source-and-tools.txt) · [Applied diff](applied.patch)
- Final runs set `PROJECT_VER=v1.5.0` for both builds. The source-only patch had made CMake label the candidate firmware `v1.5.0-dirty` in the preliminary runs. After standardizing the metadata, all 1,024 shared compile commands matched after normalizing worktree and build paths. The candidate had one additional command, for the QACC assembly file. [Compiler command check](compiler-options-check.txt) · [Preliminary comparison](default-version/comparison.json)

## Implementation reviewed

| Source | Change |
|---|---|
| `CMakeLists.txt` S3 source list | Adds the QACC assembly helper to the ESP32-S3 build. |
| `src/common/esp_nn_mean_s8_esp32s3.c` lines 49–64 and 81–106 | Adds signed 20-bit unpacking and dispatch for aligned, nonoverlapping inputs with 16-channel groups and 1–4095 spatial elements. Reuses stock requantization and retains the scalar fallback. |
| `src/common/esp_nn_mean_qacc_s8_esp32s3.S` lines 13–33 | Broadcasts +1, clears QACC, then uses a hardware loop with `ee.vld.128.xp` and `ee.vmulas.s8.qacc` to accumulate 16 signed channel sums at once. Stores the two packed halves at raw-buffer offsets 0/16 and 32/48. |

The signed 20-bit range is −524,288 through 524,287. At 4,095 elements, input extremes sum to −524,160 and +520,065, within this range. Zero-point correction is applied after extraction, followed by the stock quantizer and output clamp. The input stride and base alignment keep every vector load aligned, and scalar byte stores accommodate unaligned outputs. The C overlap gate preserves the stock traversal for overlapping buffers. [ESP-DL packing and alignment precedent](https://github.com/espressif/esp-dl/blob/master/esp-dl/dl/base/isa/tie728/dl_tie728_s8_avg_pool2d.S) · [ESP-DL unpacking precedent](https://github.com/espressif/esp-dl/blob/master/esp-dl/dl/base/dl_base_avg_pool2d.cpp)

## Target build and correctness

| Check | Actual result | Evidence |
|---|---|---|
| Supplied host emulation | 800 cases, 173 SIMD-eligible, 0 mismatches. Software QACC and stand-in quantizer. | [Host log](host-emulated.log) |
| ESP32-S3 build | Candidate `test_app` and both `bench_app` images built. The QACC helper assembled and linked into the candidate. | [Test build](candidate-test-build.log) · [Stock benchmark build](stock-bench-build.log) · [Candidate benchmark build](candidate-bench-build.log) · [Firmware hashes](firmware-sha256.txt) |
| Unchanged official `test_app` on the board | 580 passed, 0 failed, 0 skipped, `TEST_RESULT: PASS`. All 10 mean cases passed. | [Complete candidate test log](candidate-test.log) |
| Separate board correctness check, after the official suite | All 16 raw lane sums matched at area 4,095, including the −128 and +127 extremes. The aligned raw address was `0x3fca7490`, exactly 40 expected bytes changed, and padding and guards stayed intact. The full output also matched ANSI at area 4,095, area 4,096 on scalar fallback, and area 4,095 with a one-byte-misaligned scalar input. | [Edge-check log](edge-check.log) · [Edge-check source](../edge_check/main/main.c) |

## Footprint

| Footprint | Stock | Candidate | Delta |
|---|---:|---:|---:|
| Mean C object text | 978 B | 1,478 B | +500 B |
| QACC assembly object text | 0 B | 40 B | +40 B |
| Linked benchmark ELF text | 232,901 B | 233,437 B | +536 B |
| Linked ELF data | 56,464 B | 56,464 B | 0 B |
| Linked ELF BSS | 508,713 B | 508,713 B | 0 B |
| Mean stack frames, scalar fallback | 96 B | 144 B | +48 B |
| Mean stack frames, worst candidate call chain | 96 B | 144 B + 32 B helper | +80 B |

The raw dump uses a single 64-byte, 16-byte-aligned stack buffer, included in the caller frame. The candidate adds zero heap or static allocations. The public scratch getter still returns zero. [ELF sizes, symbols and stack prologues](footprint.txt)

## Official benchmark verdict — WIN

**BENCHMARKED.** The eligible `7×7×16` case is **2.1846× faster**, using **54.23% fewer cycles**. The `14×14×120` case ran the scalar fallback because 120 is not divisible by 16. Its repeatable 56-cycle decrease (~0.067%) is a measured result for the patched build, with no QACC contribution.

Each row below compares stock's optimized cycle count with the candidate's optimized count. The final sequence was stock → candidate → stock → candidate, with a flash and full boot for each. Each boot used the official benchmark's nine calls per variant and its built-in selection of the fastest call after the first. Both mean rows returned `result=ok` across all four boots.

| Official shape | mem | Stock opt median (observed range) | Candidate opt median (observed range) | Speedup | Cycles reduced | Result | Verdict |
|---|---|---:|---:|---:|---:|---|---|
| 7×7×16 | `int` | 3,585 (3,585–3,585) | 1,641 (1,641–1,641) | 2.1846× | 54.23% | `ok` | WIN |
| 14×14×120 | `int` | 83,691 (83,691–83,691) | 83,635 (83,635–83,635) | 1.0007× | 0.07% | `ok` | WIN, 56 cycles on scalar fallback |

Speedup is stock median divided by candidate median. Cycle reduction is the saved cycles divided by stock median.

## Whole-suite regression scan

Each of the four final boots finished with `BENCH_DONE cases=40 failures=0 skipped=0` and logged 55 timed variant rows. All rows matched by operation, variant, actual memory placement and shape, and all returned `result=ok`. Outside the two mean rows, 51 of 53 rows had identical optimized cycle counts on every boot.

| Other row with changed cycles | Actual placement | Stock opt cycles | Candidate opt cycles | Observation |
|---|---|---|---|---|
| Average pool, 12×12×128, 5×5, pad 2, stride 1 | `ext` | 948,108 / 948,108 | 948,109 / 948,109 | +1 cycle, about +0.00011%. |
| Batched fully connected, batch 64, length 128, 256 outputs, `esp_nn` | `int` | 2,462,350 / 2,462,350 | 2,462,344 / 2,462,343 | Median 6.5 cycles lower. The ranges overlapped in the preliminary runs. |

There were no material regressions. The unchanged fully connected performance warning appeared on each boot for length 320, 320 outputs, input offset −3. It reported 353,738 cycles at normal alignment versus 311,644 cycles for its 8-mod-16 comparison. Both firmware builds also logged the same physical 8 MiB flash versus configured 2 MiB image-header warning. PSRAM was detected and the measured memory placements agreed across the builds.

## Evidence and reproduction

- Complete serial logs in run order [stock 1](stock-bench-1.log) · [candidate 1](candidate-bench-1.log) · [stock 2](stock-bench-2.log) · [candidate 2](candidate-bench-2.log)
- Combined analysis inputs [stock.log](stock.log) · [mean.log](mean.log) · [all 55 rows with individual cycles](comparison.json)
- Local source status [clean stock](stock-status.txt) · [candidate diff summary](candidate-diff-stat.txt) · [candidate source status](candidate-status.txt) · [original Opt1/Opt2 branch](opt2-branch-status.txt)

Use two worktrees whose final directory component is named `esp-nn` so the unchanged ESP-IDF apps resolve their local component name. This workspace uses `mean-stock/esp-nn` and `mean-candidate/esp-nn`. After activating the recorded ESP-IDF checkout, run the following commands in each worktree's `bench_app`. Set the target only when initializing its build. Flash and capture the complete logs through `BENCH_DONE` in alternating order.

```sh
idf.py --ccache -D PROJECT_VER=v1.5.0 set-target esp32s3 build
idf.py --ccache -p /dev/ttyACM0 flash monitor
```

The unchanged candidate `test_app` uses the same target and flash commands. The separate `edge_check` app can be built from the kit with `idf.py --ccache set-target esp32s3 build` and uses the candidate worktree. It contains correctness checks only. In the kit directory the supplied analyzer reads the concatenated raw logs.

```sh
python3 scripts/compare_official_bench.py --stock results/stock.log --candidate results/mean.log --output results/comparison.json
```

These results cover the two official mean shapes on one ESP32-S3-EYE, with two final boots per firmware. They do not measure full-model inference or other mean shapes. The board remains flashed with the EXP-MEAN benchmark.
