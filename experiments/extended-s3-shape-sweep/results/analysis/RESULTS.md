# ESP32-S3-EYE extended INT8 shape sweep

**All 540 case executions passed ANSI output and guard checks.** This is a separate research sweep using Espressif's unchanged timing harness.

- **EXP-MEAN — MIXED.** It won 28 of 42 mean configurations, including 28 of 31 eligible for QACC. Its 4.041× eligible geometric mean shows that the gain generalizes beyond the original case, but three eligible small internal-RAM reductions and one scalar fallback lost. Keep it as an experiment. Before proposing it upstream, address the small-area dispatch losses and validate the fallback overhead.
- **Opt2 — WIN.** It won 42 of 48 max-pool configurations, with zero losses beyond 1%. All 32 sliding-path cases won. Ten additional wins came from Opt1's 128-bit path in the combined build. The sliding-path result generalizes across both filter sizes and memory classes. Keep it and consider an upstream proposal, with the dispatch constraints and the measured neutral cases documented.

## Summary

WIN means more than 1% fewer cycles than stock. LOSS means more than 1% more cycles. NEUTRAL is within ±1%, inclusive. For each build and shape, the compared value is the median of its two observed cycle counts.

| Build | Target cases | Wins | Losses | Neutral | Median speedup, all | Eligible median | Eligible geomean |
|---|---:|---:|---:|---:|---:|---:|---:|
| EXP-MEAN | 42 | 28 | 4 | 10 | 2.235× | 5.393× | 4.041× |
| Opt2 | 48 | 42 | 0 | 6 | 4.960× | 7.972× | 6.475× |

| Build | Memory | Cases | All W / L / N | Eligible W / L / N | Eligible geomean |
|---|---|---:|---:|---:|---:|
| EXP-MEAN | Internal | 31 | 19 / 4 / 8 | 19 / 3 / 0 | 4.208× |
| EXP-MEAN | PSRAM | 11 | 9 / 0 / 2 | 9 / 0 / 0 | 3.658× |
| Opt2 | Internal | 34 | 28 / 0 / 6 | 20 / 0 / 0 | 8.141× |
| Opt2 | PSRAM | 14 | 14 / 0 / 0 | 12 / 0 / 0 | 4.420× |

### EXP-MEAN

Best was internal-RAM **63×65×16**, **213,977 → 13,779 cycles (15.529×)**. The same shape in PSRAM went **337,769 → 180,070 (1.876×)**. The 4,095-element tensor is eligible for QACC, while the 4,096-element case falls back to scalar. Original-case landmarks were **3,585 → 1,641 (2.185×)** for internal 7×7×16 and **83,691 → 83,635 (NEUTRAL)** for internal 14×14×120, which still takes the scalar fallback.

All losses were in internal RAM. Each of these cycle counts repeated identically on its two boots.

| Case (H×W×C) | Path | Stock cycles | EXP-MEAN cycles | Speedup | Cycles increased |
|---|---|---:|---:|---:|---:|
| 1×1×16 | QACC SIMD | 1,085 | 1,496 | 0.7253× | 37.88% |
| 2×2×16 | QACC SIMD | 1,245 | 1,506 | 0.8267× | 20.96% |
| 3×3×16 | QACC SIMD | 1,505 | 1,521 | 0.9895× | 1.06% |
| 8×8×8 | Scalar fallback | 2,223 | 2,250 | 0.9880× | 1.21% |

The QACC setup, packed-store and unpack costs are plausible reasons the 1-, 4- and 9-element reductions lose. The experiment did not time those stages separately. The remaining 28 eligible cases all won, including all nine eligible PSRAM cases. Of 11 scalar fallbacks, ten were neutral.

### Opt2

Best was PSRAM **32×32×16, 5×5 SAME stride 1**, **399,322 → 33,605 cycles (11.883×)**. The smallest sliding-path win was PSRAM **32×32×128, 3×3 SAME stride 1**, **1,852,896 → 1,183,217 (1.566×)**. The original-case landmarks were **60,506 → 7,303 (8.285×)** for the 3×3 case in internal RAM, and **373,662 → 38,276 (9.762×)** for the 5×5 case in PSRAM.

The worst overall row was internal **16×16×8, 3×3 SAME stride 1**, **36,014 → 36,281 (0.9926×, 0.74% more cycles)**. It used the stock-width SIMD fallback and is **NEUTRAL** by the stated rule. All other cases that kept stock-width SIMD or ANSI fallback were also neutral. All eight internal and two PSRAM cases routed to Opt1's 128-bit fallback won. Those ten wins are due to the combined branch and do not exercise the sliding path.

### Controls and repeatability

All 48 max-pool controls in the EXP-MEAN build and all 42 mean controls in the Opt2 build were neutral. The Opt2 mean controls were cycle-identical to stock. None of the non-neutral target rows had overlapping stock and candidate observed ranges. Two boots per build show the observed spread and do not establish a statistical confidence interval. The CSV and JSON retain every within-band change as well as all wins and losses.

## Verification and runtime

The three detached worktrees used these exact commits.

| Build | Revision |
|---|---|
| Stock v1.5.0 | ace42ac7721119cd543fc40ffe719e601fa8f20f |
| EXP-MEAN | 4bfa49c64a932f700688c2007a01d8ea1fa102ac |
| Opt2 | edb003c6770491abb74766835f4c803b9d4f5a20 |

- Physical ESP32-S3-EYE, ESP32-S3 QFN56 rev v0.2 on /dev/ttyACM0 (USB Serial/JTAG). CPU 240 MHz, 8 MiB octal PSRAM at 80 MHz, 64 KiB 8-way D-cache with 64-byte lines, 16 KiB 8-way I-cache with 32-byte lines.
- ESP-IDF v5.5.1-dirty at fcae32885b0296b32044cb99ecbdc50d98dddb83, with pre-existing tracked edits in two example apps. Xtensa GCC 14.2.0. All 1,026 shared compile commands matched after normalizing worktree paths. EXP-MEAN adds one command for its assembly helper.
- Identical final SDK config SHA-256: 360307cc5f1d2bdbf5bc0f36a20332008d9a57d49f1f66f6234030ab3241229b. The four kit selection/source files matched across builds. The vendor timing harness and header were byte-identical to their Git versions. No optimizer or user branch changed.
- Each capture reported 90 cases, zero failures and zero skips. The harness used 16-byte-aligned disjoint buffers, seed 0xc0ffee42, and nine calls per variant. It measured the fastest of eight post-warm-up calls, with interrupts disabled during timing and output parity and guard checks intact. Paths in the results are classifications from source gates and allocation guarantees. No dispatch instrumentation was inserted.
- PSRAM cases used PSRAM and internal cases used internal memory. All six boots gave the same flash-capacity warning (8 MiB actual, 2 MiB image header). This did not affect case completion.

| Order | Firmware | Boot | Host monitor elapsed, excluding flash/build |
|---:|---|---:|---|
| 1 | Stock | 1 | 12.76 s · [serial](../stock-1.log) |
| 2 | EXP-MEAN | 1 | 12.52 s · [serial](../exp_mean-1.log) |
| 3 | Opt2 | 1 | 12.31 s · [serial](../opt2-1.log) |
| 4 | Stock | 2 | 12.75 s · [serial](../stock-2.log) |
| 5 | Opt2 | 2 | 12.31 s · [serial](../opt2-2.log) |
| 6 | EXP-MEAN | 2 | 12.78 s · [serial](../exp_mean-2.log) |

The 20-minute limit was never reached. Monitor times include startup and cleanup. The benchmark is warm-cache and uses representative fixed random inputs. It does not measure model latency, deliberate pointer misalignment, overlapping tensors, or other boards.

### Recovering the largest internal-RAM case

All six preliminary boots with the kit's 16 KiB worker stack, and one follow-up stock probe on the existing main task with the default config, skipped internal 32×32×64 max pooling (3×3, stride 1, pad 1). The probe's largest internal allocation was 319,488 bytes. The case needs two inputs, one guarded output and two internal reference outputs of 65,536 bytes each, or 327,808 bytes before allocator overhead.

For the six accepted runs, the experimental wrapper uses the existing core-0 main task at priority 5. All three configs enabled ESP-IDF's non-ISR FreeRTOS and heap routine placement into flash to recover internal RAM. All six accepted boots reported a largest internal block of 335,872 bytes before the sweep and a main-task stack high-water mark of 1,764 bytes afterward. The 64 KiB D-cache, clock, PSRAM configuration, shapes, tensor allocations and vendor timing remained the same. The preliminary logs are retained separately and were excluded from statistics. [Wrapper patch](../main-task-wrapper.patch) · [Config diff](../ram-config.diff) · [Preliminary six boots](../initial-worker-stack/) · [Main-task-only probe](../main-task-default-ram/) · [ESP-IDF RAM guide](https://docs.espressif.com/projects/esp-idf/en/release-v5.5/esp32s3/api-guides/performance/ram-usage.html)

### Reproduce

Create the three detached worktrees with the kit's installer. Apply the archived wrapper patch to each installed experimental app, and copy in the final SDK config after initializing the ESP32-S3 target. Rebuild with the same ESP-IDF and PROJECT_VER=v1.5.0. The final driver flashes and records two boots in the stated order. The kit comparator validates the logs, and the [supplemental analyzer](../analyze-validated-results.py) adds the exact cycle thresholds, path classifications and aggregate statistics.

[90-case CSV](comparison.csv) · [JSON with individual boots and reductions](comparison.json) · [Manifest](../SHAPES.json) · [Final SDK config](../stock.sdkconfig) · [Source and compiler evidence](../source-and-compile-integrity.txt) · [Toolchain and board setup](../setup.txt) · [Production diffs](../production-diffs.txt) · [Final run driver](../run-main-task-sweep.sh)

## Complete 90-case table

Mean input shapes are height × width × channels. Pool input shapes are width × height × channels. Cycle columns show the per-build medians. Target speedup and verdict compare EXP-MEAN to stock on mean, or Opt2 to stock on max pool.

| Operation | Shape | Mem | Stock cycles | EXP-MEAN cycles | Opt2 cycles | Target path | Speedup | Cycle reduction | Verdict | Correctness |
|---|---|---|---:|---:|---:|---|---:|---:|---|---|
| max_pool | input 12x12x128, filter 5x5, pad 2, stride 1 | ext | 373662 | 373662 | 38276 | Opt2 sliding SIMD | 9.7623× | +89.76% | WIN | PASS |
| max_pool | input 12x12x128, filter 5x5, pad 2, stride 1 | int | 373570 | 373570 | 38109 | Opt2 sliding SIMD | 9.8027× | +89.80% | WIN | PASS |
| max_pool | input 12x12x16, filter 5x5, pad 2, stride 1 | int | 52522 | 52522 | 5265 | Opt2 sliding SIMD | 9.9757× | +89.98% | WIN | PASS |
| max_pool | input 12x12x32, filter 5x5, pad 2, stride 1 | int | 98386 | 98386 | 9957 | Opt2 sliding SIMD | 9.8811× | +89.88% | WIN | PASS |
| max_pool | input 12x12x64, filter 5x5, pad 2, stride 1 | int | 190114 | 190114 | 19342 | Opt2 sliding SIMD | 9.8291× | +89.83% | WIN | PASS |
| max_pool | input 16x16x12, filter 3x3, pad 1, stride 1 | int | 82794 | 82794 | 82801 | 32-bit SIMD | 0.9999× | -0.01% | NEUTRAL | PASS |
| max_pool | input 16x16x120, filter 5x5, pad 2, stride 1 | int | 644342 | 644342 | 644609 | 64-bit SIMD | 0.9996× | -0.04% | NEUTRAL | PASS |
| max_pool | input 16x16x128, filter 3x3, pad 1, stride 1 | int | 403394 | 403394 | 53447 | Opt2 sliding SIMD | 7.5476× | +86.75% | WIN | PASS |
| max_pool | input 16x16x15, filter 3x3, pad 1, stride 1 | int | 438801 | 438801 | 438808 | ANSI fallback | 1.0000× | -0.00% | NEUTRAL | PASS |
| max_pool | input 16x16x16, filter 2x2, pad 0, stride 2 | int | 11842 | 11842 | 7060 | Opt1 128-bit SIMD fallback | 1.6773× | +40.38% | WIN | PASS |
| max_pool | input 16x16x16, filter 3x3, pad 0, stride 1 | int | 48122 | 48122 | 25626 | Opt1 128-bit SIMD fallback | 1.8779× | +46.75% | WIN | PASS |
| max_pool | input 16x16x16, filter 3x3, pad 1, stride 1 | ext | 60506 | 60506 | 7303 | Opt2 sliding SIMD | 8.2851× | +87.93% | WIN | PASS |
| max_pool | input 16x16x16, filter 3x3, pad 1, stride 1 | int | 60506 | 60506 | 7303 | Opt2 sliding SIMD | 8.2851× | +87.93% | WIN | PASS |
| max_pool | input 16x16x16, filter 3x3, pad 1, stride 2 | int | 15384 | 15384 | 8398 | Opt1 128-bit SIMD fallback | 1.8319× | +45.41% | WIN | PASS |
| max_pool | input 16x16x16, filter 5x5, pad 2, stride 1 | int | 95898 | 95898 | 8949 | Opt2 sliding SIMD | 10.7161× | +90.67% | WIN | PASS |
| max_pool | input 16x16x24, filter 3x3, pad 1, stride 1 | int | 84998 | 84998 | 85265 | 64-bit SIMD | 0.9969× | -0.31% | NEUTRAL | PASS |
| max_pool | input 16x16x31, filter 3x3, pad 1, stride 1 | int | 893841 | 893841 | 893848 | ANSI fallback | 1.0000× | -0.00% | NEUTRAL | PASS |
| max_pool | input 16x16x32, filter 2x2, pad 0, stride 2 | int | 20546 | 20546 | 9620 | Opt1 128-bit SIMD fallback | 2.1358× | +53.18% | WIN | PASS |
| max_pool | input 16x16x32, filter 3x3, pad 1, stride 1 | ext | 109490 | 109490 | 13895 | Opt2 sliding SIMD | 7.8798× | +87.31% | WIN | PASS |
| max_pool | input 16x16x32, filter 3x3, pad 1, stride 1 | int | 109490 | 109490 | 13896 | Opt2 sliding SIMD | 7.8792× | +87.31% | WIN | PASS |
| max_pool | input 16x16x32, filter 5x5, pad 0, stride 1 | int | 111490 | 111490 | 47166 | Opt1 128-bit SIMD fallback | 2.3638× | +57.69% | WIN | PASS |
| max_pool | input 16x16x48, filter 5x5, pad 2, stride 1 | int | 264650 | 264650 | 25429 | Opt2 sliding SIMD | 10.4074× | +90.39% | WIN | PASS |
| max_pool | input 16x16x64, filter 3x3, pad 1, stride 1 | int | 207458 | 207458 | 27079 | Opt2 sliding SIMD | 7.6612× | +86.95% | WIN | PASS |
| max_pool | input 16x16x64, filter 3x3, pad 1, stride 2 | int | 52122 | 52122 | 20047 | Opt1 128-bit SIMD fallback | 2.6000× | +61.54% | WIN | PASS |
| max_pool | input 16x16x64, filter 5x5, pad 2, stride 1 | ext | 349026 | 349026 | 33669 | Opt2 sliding SIMD | 10.3664× | +90.35% | WIN | PASS |
| max_pool | input 16x16x64, filter 5x5, pad 2, stride 1 | int | 349026 | 349026 | 33669 | Opt2 sliding SIMD | 10.3664× | +90.35% | WIN | PASS |
| max_pool | input 16x16x8, filter 3x3, pad 1, stride 1 | int | 36014 | 36014 | 36281 | 64-bit SIMD | 0.9926× | -0.74% | NEUTRAL | PASS |
| max_pool | input 24x24x128, filter 3x3, pad 1, stride 1 | ext | 1.04422e+06 | 1.04422e+06 | 602781 | Opt2 sliding SIMD | 1.7323× | +42.27% | WIN | PASS |
| max_pool | input 24x24x64, filter 5x5, pad 2, stride 1 | ext | 870397 | 870397 | 194692 | Opt2 sliding SIMD | 4.4706× | +77.63% | WIN | PASS |
| max_pool | input 2x2x16, filter 3x3, pad 1, stride 1 | int | 922 | 922 | 691 | Opt1 128-bit SIMD fallback | 1.3343× | +25.05% | WIN | PASS |
| max_pool | input 32x32x128, filter 2x2, pad 0, stride 2 | ext | 623118 | 623118 | 484142 | Opt1 128-bit SIMD fallback | 1.2871× | +22.30% | WIN | PASS |
| max_pool | input 32x32x128, filter 3x3, pad 1, stride 1 | ext | 1.8529e+06 | 1.8529e+06 | 1.18322e+06 | Opt2 sliding SIMD | 1.5660× | +36.14% | WIN | PASS |
| max_pool | input 32x32x128, filter 5x5, pad 2, stride 1 | ext | 3.10445e+06 | 3.10445e+06 | 1.21955e+06 | Opt2 sliding SIMD | 2.5456× | +60.72% | WIN | PASS |
| max_pool | input 32x32x16, filter 3x3, pad 1, stride 1 | int | 244762 | 244762 | 26727 | Opt2 sliding SIMD | 9.1579× | +89.08% | WIN | PASS |
| max_pool | input 32x32x16, filter 5x5, pad 2, stride 1 | ext | 399322 | 399322 | 33605 | Opt2 sliding SIMD | 11.8828× | +91.58% | WIN | PASS |
| max_pool | input 32x32x32, filter 3x3, pad 1, stride 1 | int | 445106 | 445106 | 52199 | Opt2 sliding SIMD | 8.5271× | +88.27% | WIN | PASS |
| max_pool | input 32x32x64, filter 2x2, pad 0, stride 2 | ext | 303100 | 303100 | 229442 | Opt1 128-bit SIMD fallback | 1.3210× | +24.30% | WIN | PASS |
| max_pool | input 32x32x64, filter 3x3, pad 1, stride 1 | int | 845794 | 845794 | 103143 | Opt2 sliding SIMD | 8.2002× | +87.81% | WIN | PASS |
| max_pool | input 4x4x16, filter 3x3, pad 1, stride 1 | int | 3626 | 3626 | 799 | Opt2 sliding SIMD | 4.5382× | +77.96% | WIN | PASS |
| max_pool | input 4x4x16, filter 5x5, pad 2, stride 1 | int | 4746 | 4746 | 2619 | Opt1 128-bit SIMD fallback | 1.8121× | +44.82% | WIN | PASS |
| max_pool | input 5x5x16, filter 3x3, pad 1, stride 1 | int | 5704 | 5704 | 1077 | Opt2 sliding SIMD | 5.2962× | +81.12% | WIN | PASS |
| max_pool | input 64x64x16, filter 3x3, pad 1, stride 1 | ext | 1.08107e+06 | 1.08105e+06 | 372947 | Opt2 sliding SIMD | 2.8987× | +65.50% | WIN | PASS |
| max_pool | input 64x64x16, filter 5x5, pad 2, stride 1 | ext | 1.7315e+06 | 1.7315e+06 | 374534 | Opt2 sliding SIMD | 4.6231× | +78.37% | WIN | PASS |
| max_pool | input 64x64x32, filter 3x3, pad 1, stride 1 | ext | 1.98734e+06 | 1.98736e+06 | 1.1595e+06 | Opt2 sliding SIMD | 1.7140× | +41.66% | WIN | PASS |
| max_pool | input 6x6x16, filter 5x5, pad 2, stride 1 | int | 11818 | 11818 | 1599 | Opt2 sliding SIMD | 7.3909× | +86.47% | WIN | PASS |
| max_pool | input 7x7x16, filter 3x3, pad 1, stride 1 | int | 11312 | 11312 | 1777 | Opt2 sliding SIMD | 6.3658× | +84.29% | WIN | PASS |
| max_pool | input 7x7x16, filter 5x5, pad 2, stride 1 | int | 16572 | 16572 | 2055 | Opt2 sliding SIMD | 8.0642× | +87.60% | WIN | PASS |
| max_pool | input 8x8x16, filter 3x3, pad 1, stride 1 | int | 14842 | 14842 | 2199 | Opt2 sliding SIMD | 6.7494× | +85.18% | WIN | PASS |
| mean | input 14x14x120 | ext | 83691 | 83635 | 83691 | scalar fallback | 1.0007× | +0.07% | NEUTRAL | PASS |
| mean | input 14x14x120 | int | 83691 | 83635 | 83691 | scalar fallback | 1.0007× | +0.07% | NEUTRAL | PASS |
| mean | input 14x14x128 | ext | 89265 | 15991 | 89265 | QACC SIMD | 5.5822× | +82.09% | WIN | PASS |
| mean | input 14x14x128 | int | 89265 | 15991 | 89265 | QACC SIMD | 5.5822× | +82.09% | WIN | PASS |
| mean | input 14x14x16 | int | 11229 | 2082 | 11229 | QACC SIMD | 5.3934× | +81.46% | WIN | PASS |
| mean | input 14x14x32 | int | 22377 | 4069 | 22377 | QACC SIMD | 5.4994× | +81.82% | WIN | PASS |
| mean | input 14x14x64 | int | 44673 | 8043 | 44673 | QACC SIMD | 5.5543× | +82.00% | WIN | PASS |
| mean | input 1x1024x16 | ext | 54285 | 4566 | 54285 | QACC SIMD | 11.8890× | +91.59% | WIN | PASS |
| mean | input 1x1x16 | int | 1085 | 1496 | 1085 | QACC SIMD | 0.7253× | -37.88% | LOSS | PASS |
| mean | input 1x256x16 | int | 14349 | 2262 | 14349 | QACC SIMD | 6.3435× | +84.24% | WIN | PASS |
| mean | input 1x256x64 | int | 57153 | 8763 | 57153 | QACC SIMD | 6.5221× | +84.67% | WIN | PASS |
| mean | input 28x28x16 | int | 41805 | 3846 | 41805 | QACC SIMD | 10.8697× | +90.80% | WIN | PASS |
| mean | input 28x28x32 | ext | 83529 | 7597 | 83529 | QACC SIMD | 10.9950× | +90.90% | WIN | PASS |
| mean | input 28x28x32 | int | 83529 | 7597 | 83529 | QACC SIMD | 10.9950× | +90.90% | WIN | PASS |
| mean | input 28x28x64 | ext | 290925 | 147440 | 290925 | QACC SIMD | 1.9732× | +49.32% | WIN | PASS |
| mean | input 28x28x64 | int | 166977 | 15099 | 166977 | QACC SIMD | 11.0588× | +90.96% | WIN | PASS |
| mean | input 2x2x16 | int | 1245 | 1506 | 1245 | QACC SIMD | 0.8267× | -20.96% | LOSS | PASS |
| mean | input 32x32x128 | ext | 5.64976e+06 | 1.41914e+06 | 5.64976e+06 | QACC SIMD | 3.9811× | +74.88% | WIN | PASS |
| mean | input 32x32x16 | int | 54285 | 4566 | 54285 | QACC SIMD | 11.8890× | +91.59% | WIN | PASS |
| mean | input 32x32x32 | int | 108489 | 9037 | 108489 | QACC SIMD | 12.0050× | +91.67% | WIN | PASS |
| mean | input 32x32x64 | int | 216897 | 17979 | 216897 | QACC SIMD | 12.0639× | +91.71% | WIN | PASS |
| mean | input 3x3x16 | int | 1505 | 1521 | 1505 | QACC SIMD | 0.9895× | -1.06% | LOSS | PASS |
| mean | input 4x4x16 | int | 1869 | 1542 | 1869 | QACC SIMD | 1.2121× | +17.50% | WIN | PASS |
| mean | input 63x65x16 | ext | 337769 | 180070 | 337769 | QACC SIMD | 1.8758× | +46.69% | WIN | PASS |
| mean | input 63x65x16 | int | 213977 | 13779 | 213977 | QACC SIMD | 15.5292× | +93.56% | WIN | PASS |
| mean | input 64x64x16 | ext | 339954 | 339985 | 339954 | scalar fallback | 0.9999× | -0.01% | NEUTRAL | PASS |
| mean | input 64x64x16 | int | 214029 | 214047 | 214029 | scalar fallback | 0.9999× | -0.01% | NEUTRAL | PASS |
| mean | input 7x7x128 | int | 28113 | 12463 | 28113 | QACC SIMD | 2.2557× | +55.67% | WIN | PASS |
| mean | input 7x7x16 | ext | 3585 | 1641 | 3585 | QACC SIMD | 2.1846× | +54.23% | WIN | PASS |
| mean | input 7x7x16 | int | 3585 | 1641 | 3585 | QACC SIMD | 2.1846× | +54.23% | WIN | PASS |
| mean | input 7x7x256 | int | 56145 | 24831 | 56145 | QACC SIMD | 2.2611× | +55.77% | WIN | PASS |
| mean | input 7x7x32 | ext | 7089 | 3187 | 7089 | QACC SIMD | 2.2243× | +55.04% | WIN | PASS |
| mean | input 7x7x32 | int | 7089 | 3187 | 7089 | QACC SIMD | 2.2243× | +55.04% | WIN | PASS |
| mean | input 7x7x64 | ext | 14097 | 6279 | 14097 | QACC SIMD | 2.2451× | +55.46% | WIN | PASS |
| mean | input 7x7x64 | int | 14097 | 6279 | 14097 | QACC SIMD | 2.2451× | +55.46% | WIN | PASS |
| mean | input 8x8x12 | int | 3294 | 3318 | 3294 | scalar fallback | 0.9928× | -0.73% | NEUTRAL | PASS |
| mean | input 8x8x15 | int | 4278 | 4306 | 4278 | scalar fallback | 0.9935× | -0.65% | NEUTRAL | PASS |
| mean | input 8x8x17 | int | 4703 | 4729 | 4703 | scalar fallback | 0.9945× | -0.55% | NEUTRAL | PASS |
| mean | input 8x8x24 | int | 6507 | 6523 | 6507 | scalar fallback | 0.9975× | -0.25% | NEUTRAL | PASS |
| mean | input 8x8x31 | int | 8562 | 8579 | 8562 | scalar fallback | 0.9980× | -0.20% | NEUTRAL | PASS |
| mean | input 8x8x33 | int | 8987 | 9001 | 8987 | scalar fallback | 0.9984× | -0.16% | NEUTRAL | PASS |
| mean | input 8x8x8 | int | 2223 | 2250 | 2223 | scalar fallback | 0.9880× | -1.21% | LOSS | PASS |
