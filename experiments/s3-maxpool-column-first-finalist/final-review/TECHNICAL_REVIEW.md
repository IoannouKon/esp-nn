# ESP32-S3 MaxPool technical review

The review compares the original PR at dafea59 with the on-board finalist and a kernel-only integration patch based on the same commit. Master in the measurements is the upstream rewrite at 9fd985a. The experimental branch and raw benchmark evidence are preserved. [Full investigation and reference results](../RESULTS.md)

## Algorithm and memory order

Both versions implement NHWC signed INT8 max pooling. For each output row y, the C wrapper clips the eligible input rows to the intersection of [y − p, y + p] and the valid input rows, where p is 1 for 3×3 and 2 for 5×5. For each input column x and 16-channel group g, the leaf computes a 16-lane vertical maximum V(x,g). The horizontal output is the signed lane-wise maximum of the eligible vertical maxima for x − p through x + p. The work remains proportional to output height × width × channels × filter height.

- **Original PR.** For one output row and one group, the assembly traverses the entire width. A vertical vector load advances by the row pitch W × C between input rows. Advancing horizontally moves by C bytes. After that group finishes, the wrapper returns to the left edge for the next group. The same cache line can be visited in multiple passes for its adjacent 16-byte portions. The leaf retains running prefix maxima of the previous columns in registers. It needs no array and clamps each output.
- **Column-first ring.** For a row and a batch, process all groups of column x before moving to x + 1. A batch contains up to eight groups (128 channels). Adjacent group iterations move by 16 bytes within the same pixel on each input row and write adjacent 16-byte portions of the same output pixel. Only then do the pointers advance by a pixel. Larger channel counts repeat the row in independent batches. Vertical accesses still jump by the full row pitch. There is no vertical-history reuse between output rows.
- **Direct 32-channel 3×3 pair.** Both groups fit in the SIMD registers. The C wrapper calls a paired leaf once per full row, passing two clipped input rows for the top and bottom and three for every interior row. It increments the row pointers; no horizontal tiling or per-group C loop is involved. For a given pixel the leaf reads the two adjacent input vectors from each valid row and stores both neighboring output vectors before advancing.
- **Eligibility.** The original checks still require a 3×3 or 5×5 stride-1 SAME shape, matching input/output dimensions, input at least as large as the filter, 16-byte aligned buffers and channels divisible by 16, with disjoint tensors. The proposed leaves run only at full activation range [−128, 127], for which clamping would be the identity. A single channel group or a narrower INT8 activation interval uses the original clamped sliding leaf. The original ANSI and upstream paths still handle inputs that fail their respective gates. Dispatch uses register fit and kernel semantics, without a tensor-size cutoff.

## History, borders and register allocation

The column-first ring stores raw vertical maxima. It allocates four 128-byte planes with 16-byte alignment on the C caller's stack. 3×3 uses the first two planes, while 5×5 uses all four. Within a plane, the offset for group g is 16 × g. The array is reused across batches and output rows. Each batch seeds its active vectors before reading them. For a steady-state column, read the two or four stored vectors for the current channel group, combine them with the current vertical vector, then replace the oldest entry with one store. The replacement slot is the remaining-column count modulo two or four; the slot pointer is computed once per column and then advanced across groups.

Left padding is handled by duplicating V(0,g) into the seed state. Repeating an element does not change a max. For 5×5, ingest column one into its slot as well. Processing the remainder emits outputs at input x − p. At the right end, the 3×3 leaf emits the max of the two remaining vectors. The 5×5 leaf emits the max of the last four vectors, then the max of the newest three, dropping slot zero. No read outside the input is needed. The paired path seeds its register history with −128, consumes column zero to prime the history, then emits a final output from the carried two-column history after the loop.

| Path | SIMD register allocation | History memory |
|---|---|---|
| Original PR | q1 is the new vertical maximum, q0 is scratch/output, q2–q5 carry one- through four-column prefix maxima, and q6/q7 hold the signed activation bounds. 3×3 uses q2/q3 for history. | 0 B |
| Column-first ring | q1 is the current vertical max, and q0 and q2–q4 initially hold independent vertical loads. After vertical reduction, q2–q5 hold the preceding history vectors and their partial reductions. q0 holds the final output. q6/q7 are unused by this leaf. | 512 B fixed stack storage. The used portion is 256 B for 3×3 or 512 B for 5×5 with a full batch. |
| Direct paired row | q1/q0 are the vertical accumulators for groups 0/1. q2/q3 are the previous vertical maximum and the two-column max for group 0; q4/q5 hold the same state for group 1. q6/q7 are alternating vertical-load operands, then the two output vectors. | 0 B |

The original vertical loop loads a vector and immediately feeds its result into the serial max chain. The ring leaf specializes two or three valid rows for 3×3 and three, four or five for 5×5. It issues independent loads before consuming them, uses a separate reduction for the fourth and fifth row in 5×5, and reads the history after the vertical temporaries are dead. The pair leaf alternates the groups' loads and reductions, advances the input column between the third-row loads and their uses, and uses a hardware loop over the regular output columns. The leaf-call count changes from H × (C/16) to H × ceil(C/128) for streaming or H for the pair. The ring reduces tensor-stride revisits but adds two or four history loads and one history store per full iteration.

## Stack frames and code cost

The Xtensa windowed leaves use 64-byte frames. The pair saves a word containing −128 at a1+0 for a byte broadcast. The upper 48 bytes are reserved for register-window spills, so that word sits below the spill area. The streaming leaf makes no explicit stack loads or stores. Its aligned ring belongs to the caller and is passed in a5; it does not overlap the leaf frame or the tensor buffers. The original leaf retains the fixed frame, sentinel and argument offsets at a1+64, +68 and +72. No path needs heap allocation, global scratch, or caller-provided scratch. A target with task stacks in PSRAM would put the ring there too, which can change its performance. These board runs used internal stack memory.

| Item | Original PR | Measured experimental finalist | Kernel-only patch |
|---|---:|---:|---:|
| Source delta versus base | 99 kernel lines over master (33 C, 66 assembly) | 883 added pooling lines over the PR, including duplicate upstream and unused research paths | 288 lines over the PR (64 C, 216 assembly, 8 private-header) |
| Streaming path stack, including public wrapper and leaf | 304 B | 1,056 B | 896 B |
| Paired path stack, including public wrapper and leaf | 304 B for the equivalent V0 input | 496 B | 368 B |
| Single-group or clamped sliding path stack | 304 B | 304 B | 304 B |
| Streaming/paired assembly symbol text | No separate leaves | 1,026 B / 267 B | 1,022 B / 253 B |

Stack numbers sum the active GNU Xtensa frame sizes, excluding the surrounding caller and interrupt frames. The experimental streamer has a 240 B public wrapper, 192 B experiment dispatcher, 560 B C streaming helper and 64 B leaf. The proposed patch removes the experiment dispatcher. Its C streaming helper is 592 B including the ring. The C paired helper is 64 B, including the row descriptor, with a 64 B assembly leaf. The new assembly symbols add 1,275 B of symbol text before section alignment. [Object stack report](logs/production-stack.su) · [Experimental stack report](../logs/direct-pair-stack.su)

## Performance and repeatability

The reviewer-case data below are from the separately flashed, five-round interleave of archived master, original PR and the measured finalist. Each value is the median of the five per-boot minima. The per-boot minimum uses upstream warm-up, alternating inputs and timing code. Benchmarks verified ANSI equality, output guards and memory placement. [Raw reviewer-case interleave](../logs/interleaved-standalone)

| Shape | Memory | Master | Current PR | Direct pair | Direct change vs master | Speedup vs master |
|---|---|---:|---:|---:|---:|---:|
| 3×3, 16×16×16 | Internal RAM | 11,954 | 7,239 | 7,257 | -39.2923% | 1.6472× |
| 3×3, 16×16×16 | PSRAM | 13,087 | 7,239 | 7,257 | -44.5480% | 1.8034× |
| 5×5, 6×6×128 | PSRAM | 12,837 | 10,748 | 8,076 | -37.0881% | 1.5895× |
| 5×5, 12×12×128 | PSRAM | 54,267 | 40,069 | 33,157 | -38.9003% | 1.6367× |
| 5×5, 20×20×128 | PSRAM | 305,809 | 337,848 | 275,098 | -10.0425% | 1.1116× |
| 3×3, 32×32×64 | PSRAM | 379,449 | 443,358 | 372,967 | -1.7083% | 1.0174× |
| 3×3, 56×56×32 | PSRAM | 836,649 | 903,836 | 836,636 | -0.0016% | 1.0000× |

The two remaining losses versus master are both 3×3 PSRAM cases and both already lost under the original PR. They repeated on every boot. The measured cycle range for each mode below is a single repeated value, so observed boot-to-boot spread was zero. This establishes repeatability for the same firmware, layout and allocation order. It does not establish the exact gap for arbitrary layouts or other boards. The prior full variants matrix also reproduced both losses across five boots, with a 0.734% gap on 32×24×64 and a 1.836% gap on 256×8×64. This makes the narrow case more sensitive to the surrounding image and run than the wide case. [Five-run finalist sweep](../logs/direct-sweep/metrics.csv) · [Five-run all-variants sweep](../logs/candidate64/metrics.csv)

| Shape, PSRAM | Master, each of 5 boots | Original PR, each of 5 boots | Finalist, each of 5 boots | Finalist vs master | Finalist vs original PR |
|---|---:|---:|---:|---:|---:|
| 32×24×64 | 220,285 | 269,499 | 220,957 | +672 cycles (+0.305%) | −18.01% |
| 256×8×64 | 1,344,993 | 1,482,793 | 1,369,678 | +24,685 cycles (+1.835%) | −7.63% |

- **32×24×64.** Master/finalist recorded 808/796 PSRAM misses and 775/3,342 dependency holds. The finalist also recorded fewer retired instructions and fewer store-buffer-full stall events. In internal RAM the ranking reversed to 72,810 master versus 68,523 finalist. The data establish a placement-sensitive residual, without isolating which PSRAM access or cache interaction costs the 672 cycles.
- **256×8×64.** Master/finalist both recorded 5,636 PSRAM misses. The finalist had 473,861 store-buffer-full stall events and 10,254 dependency holds versus 422,106 and 1,719 for master, even though it retired fewer instructions. The 16 KiB row pitch puts three input rows plus one output row at 64 KiB before any alignment or conflict effects. The same-size 128×16×64, 64×32×64 and 32×64×64 shapes were at or slightly ahead of master with the finalist. Those comparisons are consistent with a wide-row throughput limit. The events come from separate profiled calls, can overlap, and do not identify individual capacity, conflict or writeback effects.

## Production diff

The proposed patch changes only the existing ESP32-S3 pooling C file, assembly file and private C/assembler layout header. It keeps the original clamped single-group leaf and uses two new private symbols. It strips the mode selector, all variants other than the two retained leaves, the renamed upstream implementation, tile/band paths, counters, tests and benchmark infrastructure. The only adaptation of the paired assembly is to specialize its first and last columns for full rows and remove general tile arguments. The streaming leaf retains the measured loop order and ring representation. [Kernel-only unified diff](production.patch)

The patch is based on dafea59. It has been checked for clean application in the PR checkout using git apply --check. The proposed change is held in a detached validation worktree.

## Validation of the kernel-only diff

The kernel-only patch passed 861 dual-core checks (45 max-pool), with zero failures or skips.
The five board boots each passed 49 benchmark cases, including the nine audited max-pool shapes.

| Shape | Memory | Kernel-only patch median | Boot samples | Archived master for reviewer cases |
|---|---|---:|---|---:|
| 3×3, 16×16×16 | Internal RAM | 7,220 | 7220 / 7220 / 7220 / 7220 / 7220 | 11,954 |
| 3×3, 16×16×16 | PSRAM | 7,220 | 7220 / 7220 / 7220 / 7220 / 7220 | 13,087 |
| 5×5, 6×6×128 | PSRAM | 8,074 | 8074 / 8074 / 8074 / 8074 / 8074 | 12,837 |
| 5×5, 12×12×128 | PSRAM | 33,239 | 33239 / 33239 / 33239 / 33239 / 33239 | 54,267 |
| 5×5, 20×20×128 | PSRAM | 275,386 | 275386 / 275386 / 275386 / 275386 / 275386 | 305,809 |
| 3×3, 32×32×64 | PSRAM | 371,191 | 371191 / 371191 / 371191 / 371191 / 371191 | 379,449 |
| 3×3, 56×56×32 | PSRAM | 836,720 | 836720 / 836720 / 836720 / 836720 / 836720 | 836,649 |
| 3×3, 32×24×64 | PSRAM | 215,915 | 215915 / 215915 / 215915 / 215915 / 215915 | — |
| 3×3, 256×8×64 | PSRAM | 1,370,659 | 1370659 / 1370659 / 1370659 / 1370659 / 1370659 | — |

All five cleanup-build samples repeated exactly, and the reference sdkconfig and both guard checks matched. The cleaned build uses the same ring and paired-row algorithms, with direct C dispatch and a full-row-only pair leaf. Its 56×56×32 result is 71 cycles slower than the archived master, roughly 0.0085%. The measured prototype was 13 cycles faster. Both are effectively at parity, and the sign at this scale is sensitive to the binary. The 32×24×64 timing also moved when built into the smaller harness. The two extended cleanup-build timings above are absolute cycles. The repeatability table uses the matched interleaved firmware for relative claims.

[Raw cleanup validation logs](logs) · [Validation setup](../REPRODUCE.md) · [Separate validation benchmark patch](../patches/validation-bench.patch)
