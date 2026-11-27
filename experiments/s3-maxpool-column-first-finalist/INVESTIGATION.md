# PR #68 max-pool locality investigation

## Baseline and hypotheses

The original ESP32-S3-EYE reproduction remains in [pr68-reviewer-repro](reference/RESULTS.md). Its master and PR implementations are 9fd985a and dafea59. This experiment uses the same board, ESP-IDF v6.1 tag, GNU Xtensa 15.2.0 toolchain, 240 MHz, octal 80 MHz PSRAM, and the default 64 KiB, 8-way, 64-byte DCache unless a cache control is labeled. The loose interrupt-watchdog deadline in the experiment accommodates the longer ANSI reference runs. Profiling samples run after the stock cycle measurement.

V0 clips the Y bounds once per output row and gives each 16-channel group an entire row in one assembly call. Its 128-bit loads and stores advance by the complete channel count at each X step. For 64-byte lines and aligned 64/128-channel tensors, a single pass consumes 16 bytes from each line it touches. Other groups consume the remaining parts later. With 16 channels, neighboring X positions in the same pass can share a line. Width, row pitch and phase between input and output allocations determine how the touched lines map to cache sets. The set index repeats every 8 KiB for the nominal 64 KiB/8-way geometry, assuming ordinary contiguous indexing. This is a model for designing comparisons.

The upstream wrapper calls a leaf for a contiguous span of output pixels or a single clipped border pixel. It uses a specialized 3×3 interior with 16-lane chunks and a 128-bit generic path which can process 64 lanes. Its channel traversal completes a pixel before progressing across the row. The rewrite reduces load-use dependencies by overlapping loads and reductions in portions of the leaf. V0 executes fewer data accesses than upstream because it reuses vertical maxima, but its inner loop streams only one group and uses back-to-back load/max pairs. V0 makes roughly H × (C/16) leaf calls on eligible shapes. Small tiles multiply this count by ceil(W/tile_width), add repeated halo columns and restart the history.

V0 uses q2–q3 for 3×3 history, q2–q5 for 5×5 history, q6/q7 for clamping, and q0/q1 for temporaries. Four independent 3×3 histories would already occupy eight vector registers. For 5×5, two histories occupy eight. Processing multiple groups in column order therefore needs a different history representation, scratch, or recomputation.

## First hardware observations

The diagnostic is a paired same-firmware run, with the upstream wrapper linked under a separate symbol and the assembly that master and PR share reused byte for byte as source. The intentionally unchanged ANSI reference and optimized output guard protocol came from the previous reproduction. The [initial diagnostic capture](logs/diagnostic64/run-1.log) contains valid measurements up to a reference interrupt-watchdog timeout on the last wide 5×5 control. The [first full variant sweep](logs/variants64/run-1.log) completed all 104 benchmark cases. The [scheduled variant pilot](logs/final64/run-1.log) completed with zero kernel failures or skips, but the serial stream dropped some benchmark records. Final cycle medians use the buffered serial capture.

In the diagnostic at default cache settings, the three large reviewer cases, in table order, had master/PR DCache PSRAM misses of 1,010/1,006, 1,301/1,301 and 3,139/3,139. The PR executed substantially fewer DBUS accesses, yet its dependency-stall counts were 12,171, 8,203 and 12,555 versus master at 1,659, 975 and 1,719. The aggregate miss count alone did not explain the regression. Equal counts leave open differences in the time spent waiting for transactions, overlap, writeback order and how misses were distributed.

Column-first V1 lowered large-map cycle counts with nearly unchanged measured DBUS traffic and miss counts, increased instruction counts, and nearly unchanged dependency-event counts. For 20×20×128 in the full prototype sweep, illustrative cycles were 306,928 master, 339,495 V0 and 291,532 V1. This ordered-access intervention isolated a useful part of the effect, but instructions retired, cache misses and store-buffer stalls are not additive decompositions of CPU cycles.

The 32 KiB 3×3 aspect controls with 64 channels had different V0/master ratios despite identical tensor bytes. For instance the diagnostic measured about 1.16× for 8×64×64 and 1.26× for 32×16×64 in PSRAM. The DRAM ratios were about 1.06× and 1.05×. The 20×20×128 5×5 case changed from about 0.71× in DRAM to 1.11× in PSRAM. Some 3×3 shapes with many groups still lost in DRAM, so on-chip compute and call overhead also matter. The tensor's byte count is insufficient to predict the result.

## Counters and timing

The ESP32-S3 EXTMEM hardware exposes DBUS PSRAM misses and total DBUS cache accesses. The Xtensa core exposes two programmable counters. Separate warmed passes select retired instructions, store-buffer-full stalls, TIE-port stalls and register-dependency holds. The recorded cache deltas come from the latter pass, and the timing median comes from the untouched timing loop. EXTMEM counts can include background traffic from the idle second core or stack/ROM accesses and do not classify individual cache evictions as capacity or conflict misses. Xtensa events reflect their defined hardware signals and can overlap. [ESP-IDF performance monitor](https://docs.espressif.com/projects/esp-idf/en/stable/esp32s3/api-reference/system/perfmon.html)

The measurement zero-interrupt region contains the tested kernel. ANSI equality and guard checks happen outside the timed region, including on the separate counter calls. Data placement is verified with IDF's memory-region predicates and actual tensor addresses are logged. Timing is reported as a median of five boot minima, with each minimum taken across eight timed calls after one warm-up. Modes alternate within each shape over the same allocated buffers.

## Interventions

| Mode | Traversal and state | Scratch |
|---|---|---:|
| V0 | One group crosses the whole row. Two or four SIMD prefix maxima remain live. | 0 B |
| V1 | Every group in a batch completes the column. The leaf loads and stores two or four prefix vectors per group. Each batch handles up to eight groups. | 512 B bounded stack allocation |
| V2 | T4, T8, T16 and T32 process one row at a time with register-resident history and clipped left/right halos per tile. | 0 B |
| V3 | B4, B8, B16 and B32 visit four neighboring output rows before moving to the next horizontal tile. They use the V2 leaf and repeat the vertical reduction per output row. | 0 B |
| V4 scheduled | Removes full-range clamps, schedules independent loads and uses separate hardware loops for history seeding and output. Border row counts are specialized. | 0 B |
| V4 paired | Extends scheduled 3×3 to two adjacent groups, with two history vectors per group. 5×5 uses the scheduled single-group leaf. | 0 B |
| V4 stream | Column-first traversal with scheduled loads and an in-DRAM ring of raw vertical maxima. Four history stores per 5×5 group become one. A single group uses the scheduled leaf. | 512 B bounded stack allocation on the ring path |
| V4 Fit0 | Retains V0 for a single group. It pairs both groups across a whole 3×3 row at 32 channels. Other eligible full-range cases use the stream ring. | 0 B for single/paired, 512 B for the ring |

The fallback for non-full activation intervals in the scheduled modes uses the
original clamped sliding implementation. The wrapper preserves disjointness,
alignment, valid dimensions, SAME padding and out-of-int8 limit handling.
Every new assembly leaf has a 64-byte frame. The stack sentinel, where used,
stays below the register-window spill area. No heap allocation or caller
scratch is required. GCC reported 192-byte and 560-byte static frames in the
experimental dispatcher and ring wrapper, respectively. A conservative bound
for these frames plus the assembly frame is 816 bytes in addition to the
public wrapper. The 560-byte frame includes the ring itself. [Stack usage](logs/kernel-c-stack.su)

At 32×32×64, T4 raises the V0 leaf count from 128 to roughly 1,024 calls
and rereads horizontal halo columns. The scheduled pilot also recorded about
151,000 retired instructions for T4 versus about 82,000 for V0 on this case.
Wider tiles reduced the excess, but the ordinary tiled paths retained
group-major order inside each tile. The experiment does not split the call
cost from the extra halo work.

The scheduled pilot cut dependency holds at 20×20×128 from roughly 12,000
to roughly 500, while a fixed tile still left a small loss versus master.
The column-first ring alone also did not reduce the measured misses across
all cases. The two interventions address different costs. Fit0 uses the
whole-row paired path when both 3×3 groups fit in the SIMD register file,
eliminating the pair experiment's repeated horizontal halos. This choice
depends on register use and the filter geometry.

## Independent cache controls

The controls change one DCache option at a time: 32 KiB with 64-byte lines, 64 KiB with 32-byte lines, and 64 KiB with four ways. For each configuration the firmware logs live capacity and line size and the associativity programmed by ESP-IDF. These are one-boot diagnostics. The default report uses five boots. [Control tables and raw logs](CACHE_CONTROLS.md)

The 32 KiB cache added about 180 PSRAM misses to the 12×12×128 case, which had zero in the 64 KiB control, and reduced V0's advantage on that shape to approximately 1%. A timed invocation uses one input and one timed output, so that pair accounts for 36 KiB before code, reference buffers and other activity. With 32-byte lines at fixed 64 KiB, the three large shapes had roughly twice as many counted PSRAM misses in both implementations. The 20×20×128 ranking reversed, even though both kernels took more cycles. Cache geometry therefore changes the observed penalty, but the measured total misses do not predict the head-to-head order on their own.

At the original 64 KiB configuration, the three large shapes had approximately 1,000, 1,300 and 3,139 PSRAM misses on both kernels. Fit0 reduced dependency holds from 12,173 to 5,614, 8,205 to 4,366, and 12,557 to 295, respectively. On the last case it nearly halved retired instructions versus V0 and still only tied master in cycles. The measurements support a combination of access order, data latency or throughput, and instruction dependencies. The counters do not directly distinguish of capacity misses, set conflicts and writeback latency.

The related aspect controls showed that one tensor's byte count is not enough. For the 64-channel 3×3 shapes with 32 KiB of input, varying width from 8 to 64 at constant total input bytes changes the active full-row input span from about 1.5 KiB to 12 KiB. The corresponding 5×5 span changes from 2.5 KiB to 20 KiB. Internal-RAM results with identical shapes remove most PSRAM misses while retaining the compute schedule and group counts. The 160-channel checks also confirm the correctness of processing in more than one batch. [Full cycle and counter data](logs/candidate64/metrics.csv)

Changing the firmware's DCache associativity setting from eight ways to four
at the original capacity and line size changed the three reviewer ratios by
less than 0.01 percentage points in this control. That weakens the explanation
that a way-capacity conflict dominates those three cases. It does not rule out
set conflicts on other pitches, placements or workloads. At 256×8×64, there
are 16 KiB per input row. Three 3×3 input rows plus one output row already span
64 KiB before accounting for line misalignment or other activity. The largest
architectural difference on this shape is that master approaches it as a
row-major pixel stream, while the experiment maintains a small scratch ring and
crosses three widely spaced input rows for each pixel. Additional traffic from
cache replacement was plausible on that shape, and V0 measured 5,897 misses
versus 5,636 for master and the streamer in the interleaved matrix.

### Equal-byte aspect controls

All inputs below are 32 KiB. The full-row spans are an analytical upper bound for a steady-state row, before cache-set and alignment effects. Ratios use the measured five-boot medians.

| Input | Filter | Input-row span | V0/master in DRAM | V0/master in PSRAM |
|---|---|---:|---:|---:|
| 8×64×64 | 3×3 | 1.5 KiB | 1.064 | 1.155 |
| 16×32×64 | 3×3 | 3.0 KiB | 1.064 | 1.214 |
| 32×16×64 | 3×3 | 6.0 KiB | 1.054 | 1.257 |
| 64×8×64 | 3×3 | 12.0 KiB | 1.026 | 1.231 |
| 64×32×16 | 3×3 | 3.0 KiB | 0.761 | 0.862 |
| 32×32×32 | 3×3 | 3.0 KiB | 0.910 | 1.103 |
| 16×16×128 | 3×3 | 6.0 KiB | 1.174 | 1.178 |
| 8×64×64 | 5×5 | 2.5 KiB | 0.690 | 0.823 |
| 16×32×64 | 5×5 | 5.0 KiB | 0.655 | 0.872 |
| 32×16×64 | 5×5 | 10.0 KiB | 0.643 | 0.861 |
| 64×8×64 | 5×5 | 20.0 KiB | 0.649 | 0.906 |
| 64×32×16 | 5×5 | 5.0 KiB | 0.245 | 0.374 |
| 32×32×32 | 5×5 | 5.0 KiB | 0.459 | 0.798 |
| 16×16×128 | 5×5 | 10.0 KiB | 0.725 | 0.933 |

## Limits of the inference

The causal interventions were traversal order, scheduled loads, tile width,
row banding, and independently selected cache settings. They show that
column-first output ordering helps the large PSRAM cases and that reducing
dependencies/call overhead helps the compute portion. They do not establish
a single cache-miss mechanism. In particular, code and PSRAM allocation
placement influence near-capacity timings, and the board's counters cannot
attribute an individual miss to a capacity limit or a set conflict. The
default-cache 256×8×64 residual merits separate attention because its unusually
wide active span stresses the cache even though its total tensor count
matches several narrower cases.

The internal-RAM cases were limited to a 51,200-byte tensor. The stock harness
allocates two inputs, one timed output and two reference outputs. Restricting
the internal configuration range kept those buffers in internal DRAM while
retaining the larger PSRAM-only controls.
