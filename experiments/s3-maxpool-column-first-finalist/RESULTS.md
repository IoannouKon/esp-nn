# ESP32-S3 max-pool regression investigation

**Recommendation for review.** Use the scheduled column-first ring with the direct paired-row leaf for 32-channel 3×3 and the existing single-group leaf. It preserves all four reviewer wins, brings two large cases 10.04% and 1.71% ahead of master, and matches master to within 13 cycles on the third. In the finalist's five-run extended matrix, it wins 62 of 64 configurations with no new losses versus master. Two pre-existing extended losses remain.

The experiments use the ESP32-S3-EYE, ESP-IDF v6.1, 240 MHz CPU, octal 80 MHz PSRAM, and the original 64 KiB, eight-way, 64-byte-line DCache. Master is Espressif's rewrite at 9fd985a. Current PR is dafea59 with the stack-frame fix. The original standalone captures and configurations are preserved. [Reference reproduction](reference/RESULTS.md)

## Reviewer cases with the original harness

The archived standalone baselines and Fit0 use the same uninstrumented timing loop, byte-identical generated sdkconfig, seed and tensor addresses. Each column is the median of five boot minima. The Fit0 confirmation boots followed the archived master/PR run. The next section reports the interleaved comparisons within one firmware.

| Shape | Memory | Archived master | Archived PR | Fit0 | Speedup vs master | Fit0 change vs PR | Fit0 samples |
|---|---|---:|---:|---:|---:|---:|---|
| 3×3, 16×16×16 | Internal RAM | 11,954 | 7,239 | 7,257 | 1.6472× | +0.25% | 7257 / 7257 / 7257 / 7257 / 7257 |
| 3×3, 16×16×16 | PSRAM | 13,087 | 7,239 | 7,257 | 1.8034× | +0.25% | 7257 / 7257 / 7257 / 7257 / 7257 |
| 5×5, 6×6×128 | PSRAM | 12,837 | 10,748 | 8,071 | 1.5905× | -24.91% | 8071 / 8071 / 8071 / 8071 / 8071 |
| 5×5, 12×12×128 | PSRAM | 54,267 | 40,069 | 33,151 | 1.6370× | -17.27% | 33151 / 33151 / 33151 / 33151 / 33151 |
| 5×5, 20×20×128 | PSRAM | 305,809 | 337,848 | 275,098 | 1.1116× | -18.57% | 275098 / 275098 / 275098 / 275098 / 275098 |
| 3×3, 32×32×64 | PSRAM | 379,449 | 443,358 | 372,967 | 1.0174× | -15.88% | 372967 / 372967 / 372967 / 372967 / 372967 |
| 3×3, 56×56×32 | PSRAM | 836,649 | 903,836 | 836,766 | 0.9999× | -7.42% | 836766 / 836766 / 836766 / 836766 / 836766 |

Fit0 preserved the four reviewer wins. On the three large cases it was 18.57%, 15.88% and 7.42% faster than the original PR. Against master, the first two gained 10.04% and 1.71%. The third was 117 cycles slower, a 0.014% residual. Every standalone benchmark boot passed 47 cases with zero failures or skips. [Standalone logs](logs/standalone64)

## Interleaved comparison and extended sweep

Each of five boots timed master, V0 and every alternative consecutively inside each shape using the same inputs, alignment and output buffer. The table shows medians of the upstream eight timed calls' minima. The best tile, band and V4 mode are selected for each row to show which ideas helped. The comparison takes the best observed candidate per row.

Cache configuration from the board was POOL_CACHE ictrl=0xb dctrl=0x15 icache_kib=16 icache_ways=8 icache_line=32 dcache_kib=64 dcache_ways_config=8 dcache_line=64 psram_mhz_config=80.

| Shape | Memory | Master | Current PR | V1 | V2 best tile | V3 best band | V4 best | Best | Speedup vs master |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|
| 3×3, 16×16×16 | Internal RAM | 11,954 | 7,252 | 10,379 | 8,863 (t16) | 8,040 (b16) | 5,673 (fit) | fit (5,673) | 2.107× |
| 3×3, 16×16×16 | PSRAM | 13,087 | 7,252 | 10,379 | 8,863 (t16) | 8,040 (b16) | 5,673 (fit) | fit (5,673) | 2.307× |
| 5×5, 6×6×128 | PSRAM | 12,837 | 10,761 | 12,078 | 10,937 (t8) | 10,658 (b8) | 7,514 (pair) | pair (7,514) | 1.708× |
| 5×5, 12×12×128 | PSRAM | 53,685 | 39,741 | 45,888 | 39,425 (t16) | 38,806 (b16) | 24,434 (pair) | pair (24,434) | 2.197× |
| 5×5, 20×20×128 | PSRAM | 307,457 | 341,093 | 292,861 | 337,435 (t32) | 333,456 (b32) | 274,986 (fit) | fit (274,986) | 1.118× |
| 3×3, 32×32×64 | PSRAM | 377,208 | 440,952 | 373,077 | 439,280 (t32) | 439,139 (b32) | 371,305 (fit) | fit (371,305) | 1.016× |
| 3×3, 56×56×32 | PSRAM | 836,646 | 903,839 | 836,673 | 895,124 (t8) | 882,494 (b8) | 836,650 (stream) | master (836,646) | 1.000× |

Measured 64 matched shapes and placements per mode.

| Implementation | Wins vs master | Ties | Losses | >1% slower than master | >1% slower than V0 | Worst ratio vs master |
|---|---:|---:|---:|---:|---:|---:|
| b16 | 33 | 0 | 31 | 31 | 45 | 1.289 |
| b32 | 35 | 0 | 29 | 29 | 31 | 1.241 |
| b4 | 12 | 0 | 52 | 51 | 61 | 1.986 |
| b8 | 26 | 0 | 38 | 36 | 57 | 1.477 |
| fit | 59 | 0 | 5 | 2 | 5 | 1.159 |
| fit0 | 59 | 0 | 5 | 2 | 5 | 1.174 |
| master | 0 | 64 | 0 | 0 | 36 | 1.000 |
| pair | 52 | 0 | 12 | 10 | 5 | 1.207 |
| sched | 47 | 0 | 17 | 16 | 5 | 1.207 |
| stream | 58 | 0 | 6 | 3 | 5 | 1.191 |
| stream0 | 58 | 0 | 6 | 3 | 5 | 1.174 |
| t16 | 31 | 0 | 33 | 33 | 50 | 1.315 |
| t32 | 34 | 0 | 30 | 28 | 39 | 1.268 |
| t4 | 11 | 0 | 53 | 52 | 60 | 2.070 |
| t8 | 24 | 0 | 40 | 40 | 58 | 1.521 |
| v0 | 37 | 0 | 27 | 26 | 0 | 1.257 |
| v1 | 38 | 0 | 26 | 22 | 39 | 1.221 |

V1 improved the three large reviewer cases, but was almost tied with master on the largest and gave up speed on the smaller cases. Horizontal tiles and row bands, in isolation, left all three large cases behind master. The scheduled and streaming variants removed more of the gap. The paired whole-row kernel substantially reduced retired instructions and dependency holds on 56×56×32, where the remaining cycles were sensitive to PSRAM behavior.

Fit0 beat master in 59 of 64 matched shape-and-memory configurations in the interleaved matrix. Five were slower, and two exceeded 1%. The largest recorded loss was 17.43% on the 64×32×16 PSRAM case near cache capacity. The 256×8×64 3×3 PSRAM case was 1.84% behind master and 7.63% ahead of V0. No allocation failures occurred in accepted benchmark captures. The widest 5×5 case slowed down substantially under some cache geometries. For that control the ANSI reference timing alone allowed interrupts to avoid starving serial output and the watchdog. Optimized timing and all correctness checks stayed the same.

[Raw five-boot matrix](logs/candidate64) · [All medians, counter values and cycle samples](logs/candidate64/metrics.csv)

## Correctness and implementation cost

All 16 PR and experimental modes passed 858 checks each, including 42 max-pool checks per mode. The archived master firmware passed its 849-check dual-core suite.

The benchmarks checked byte-exact ANSI equality and both 64-byte guards for every optimized invocation. The tests included clipped edges, rectangular and minimum-size maps, independently misaligned pointers, clamping within and outside INT8, and a second 128-channel batch. The initial shared-boot suite encountered allocation skips from mode 8 onward. Those modes passed on fresh boots and only the zero-skip passes count here.

The ring requires 512 bytes of aligned local history, backed by a 560-byte C frame. The measured static C frames for the public wrapper and experimental dispatcher are 240 and 192 bytes. Each assembly leaf has a 64-byte frame. Adding those frame sizes gives a conservative bound of 1,056 bytes including the local ring, before the external caller's frame. The single-group and paired branches need no history storage. The ring and paired leaves assemble to 1,026 and 267 bytes respectively. [Implementation rationale and stack details](INVESTIGATION.md)

## Benchmark-order probe

The 64×32×16 3×3 PSRAM loss did not recur in a focused benchmark that swaps the V0 and Fit0 order. The two kernels shared the original single-group assembly leaf. Fit0 cost nine extra cycles relative to V0 in each order. Both beat master in both orders. This demonstrates sensitivity to the surrounding run or layout. It does not identify which cache state or address mapping caused the wide-sweep result. The same firmware checked two 160-channel cases with both orders using ANSI and guard bytes.

| Group | Master | First candidate | Second candidate |
|---|---:|---:|---:|
| v0 → fit0 | 129,711 | 112,381 | 112,390 |
| fit0 → v0 | 126,462 | 108,841 | 108,832 |

[Five order-probe boots](logs/order64)

## Direct paired-row follow-up

The 32-channel 3×3 path can call the paired assembly leaf once per entire output row. The C wrapper passes two valid rows at the top and bottom and three in the interior, using pointer increments between calls. On the original standalone harness, this saved 130 cycles on the 56×56×32 case versus Fit0, reducing it to 836,636 cycles. The updated wrapper passed 861 checks, including 45 max-pool checks, with both cores active and zero failures or skips. The three added checks exercise the minimum legal height and both rectangular orientations. The direct wrapper uses the same SIMD leaf and stack frame.

[Follow-up source patch](patches/measured-standalone.patch) · [Initial five-boot confirmation](logs/pair64) · [Dual-core correctness log](logs/pair-tests/run-1.log)

### Fresh standalone interleave

Five rotating master/PR/direct-pair rounds reproduced the archived master and PR cycle counts. The three binaries used the same generated sdkconfig, and all audited tensor addresses matched across the 15 boots. The compiler commands for the shared benchmark and kernel sources matched after normalizing checkout and build paths. The build stamp in esp_app_desc.c identifies the experimental image. Every max-pool call matched ANSI and preserved both guards.

| Shape | Memory | Master | Current PR | Direct pair | Direct change vs master | Speedup vs master |
|---|---|---:|---:|---:|---:|---:|
| 3×3, 16×16×16 | Internal RAM | 11,954 | 7,239 | 7,257 | -39.2923% | 1.6472× |
| 3×3, 16×16×16 | PSRAM | 13,087 | 7,239 | 7,257 | -44.5480% | 1.8034× |
| 5×5, 6×6×128 | PSRAM | 12,837 | 10,748 | 8,076 | -37.0881% | 1.5895× |
| 5×5, 12×12×128 | PSRAM | 54,267 | 40,069 | 33,157 | -38.9003% | 1.6367× |
| 5×5, 20×20×128 | PSRAM | 305,809 | 337,848 | 275,098 | -10.0425% | 1.1116× |
| 3×3, 32×32×64 | PSRAM | 379,449 | 443,358 | 372,967 | -1.7083% | 1.0174× |
| 3×3, 56×56×32 | PSRAM | 836,649 | 903,836 | 836,636 | -0.0016% | 1.0000× |

The three large reviewer cases were 10.04% faster, 1.71% faster, and effectively tied with master. On the last case, the direct wrapper saved 67,200 cycles versus the current PR and 13 cycles versus master. The four small-case wins remained. [Raw serial logs](logs/interleaved-standalone)

### Finalist extended sweep

Five boots interleaved the direct-pair candidate, master and V0 across the same 64 shape-and-memory configurations. The reduced mode list tests the finalist under the same tensor allocations with fewer intervening kernels than the all-variants matrix. All 960 measured mode/case records and their placement audits passed. The allocation and output guard checks reported zero failures or skips on every boot.

Measured 64 matched shapes and placements per mode.

| Implementation | Wins vs master | Ties | Losses | >1% slower than master | >1% slower than V0 | Worst ratio vs master |
|---|---:|---:|---:|---:|---:|---:|
| direct | 62 | 0 | 2 | 1 | 3 | 1.018 |
| master | 0 | 64 | 0 | 0 | 36 | 1.000 |
| v0 | 37 | 0 | 27 | 26 | 0 | 1.262 |

The direct-pair finalist turned 0 V0 wins or ties against master into losses.

| Shape | Memory | Master | Current PR | Direct pair | Direct change vs master |
|---|---|---:|---:|---:|---:|
| 3×3, 32×24×64 | PSRAM | 220,285 | 269,499 | 220,957 | +0.305% |
| 3×3, 256×8×64 | PSRAM | 1,344,993 | 1,482,793 | 1,369,678 | +1.835% |

Both losses already existed in V0. The candidate reduced their cycle counts by 18.01% and 7.63%, respectively. Three shapes slowed by more than 1% relative to V0 while retaining their wins over master. The two 3×3 minimum-size cases added eight cycles each. The 5×5 32×32×32 internal-RAM case added 946 cycles and still used 53.42% fewer cycles than master. The 64×32×16 near-capacity PSRAM loss from the all-variants matrix did not recur.

The decision to use the paired leaf is based on the SIMD register fit for two 3×3 channel groups. The experiment uses no tensor-size cutoff. The production PR branch remains at dafea59.

[Finalist raw logs and CSV](logs/direct-sweep) · [Finalist sweep patch](patches/measured-sweep.patch)

## Audit trail

- [Cache controls](CACHE_CONTROLS.md) and [counter interpretation](INVESTIGATION.md)
- [Commands and worktree setup](REPRODUCE.md), [experimental patch](patches/experiment.patch), and [board and firmware identity](logs/environment.txt)
- [Baseline SHA-256 manifest](logs/reference.sha256), [stack reports](logs/kernel-c-stack.su), and [assembly symbol sizes](logs/asm-symbol-sizes.txt)
