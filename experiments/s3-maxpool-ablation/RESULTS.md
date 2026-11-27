# MaxPool ablation results

The data are from the ESP32-S3-EYE and pinned v6.1 toolchain. Each cycle value is the median of five verified boots, with the upstream within-boot timing and the same input/output placement across modes in a case. V0 is the production PR kernel selected through the common ablation wrapper. The direct label is the measured research finalist. Small cycle differences from the older standalone binaries can come from that wrapper, the firmware image or the variant order. [Method and variant definitions](ABLATION.md)

## Initial screen

The nine cases were the seven reviewer configurations and two additional 32-channel 3×3 cases. All five boots completed with zero benchmark failures or skips. The reported percentage effects are equally weighted geometric-mean cycle reductions, restricted to eligible shapes for the ring, batching and paired comparisons.

First variant per boot was e4, prefix, batch16, stream, pair_generic.

| Shape | Memory | master | v0 | e1 | e2 | e3 | e4 | prefix | batch16 | stream | pair_generic | direct |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 3×3, 16×16×16 | Internal RAM | 11,954 | 7,381 | 6,795 | 6,439 | 6,692 | 5,659 | 7,390 | 7,390 | 7,390 | 7,390 | 7,390 |
| 3×3, 16×16×16 | PSRAM | 13,087 | 7,381 | 6,795 | 6,439 | 6,692 | 5,659 | 7,390 | 7,390 | 7,390 | 7,390 | 7,390 |
| 5×5, 6×6×128 | PSRAM | 12,837 | 10,828 | 10,050 | 10,002 | 10,287 | 8,598 | 9,623 | 12,000 | 8,125 | 8,117 | 8,116 |
| 5×5, 12×12×128 | PSRAM | 53,685 | 39,844 | 37,146 | 35,898 | 37,047 | 30,270 | 39,611 | 45,996 | 32,797 | 32,789 | 32,788 |
| 5×5, 20×20×128 | PSRAM | 308,544 | 339,922 | 334,573 | 331,400 | 333,847 | 319,635 | 283,802 | 353,562 | 277,656 | 277,650 | 277,647 |
| 3×3, 32×32×64 | PSRAM | 377,061 | 440,921 | 434,414 | 429,195 | 432,268 | 419,912 | 371,152 | 458,749 | 371,176 | 371,176 | 371,176 |
| 3×3, 56×56×32 | PSRAM | 837,714 | 905,068 | 898,377 | 892,674 | 895,859 | 882,807 | 837,745 | 921,489 | 837,751 | 837,837 | 837,671 |
| 3×3, 32×32×32 | PSRAM | 116,210 | 130,744 | 126,899 | 125,295 | 126,422 | 120,431 | 106,590 | 139,935 | 108,099 | 97,315 | 93,075 |
| 3×3, 32×32×32 | Internal RAM | 57,426 | 52,469 | 48,107 | 44,643 | 46,688 | 38,439 | 51,136 | 64,547 | 52,294 | 26,993 | 22,781 |

| Mode | Geomean speedup vs master | Geomean speedup vs V0 | Wins vs master | Losses >1% | Worst vs master | Geomean cycles / oracle |
|---|---:|---:|---:|---:|---:|---:|
| master | 1.000× | 0.879× | 0/9 | 0 | 1.000× | 1.196× |
| v0 | 1.138× | 1.000× | 5/9 | 4 | 1.169× | 1.051× |
| e1 | 1.199× | 1.053× | 5/9 | 4 | 1.152× | 0.998× |
| e2 | 1.234× | 1.084× | 5/9 | 4 | 1.138× | 0.970× |
| e3 | 1.206× | 1.059× | 5/9 | 4 | 1.146× | 0.992× |
| e4 | 1.354× | 1.190× | 5/9 | 4 | 1.114× | 0.883× |
| prefix | 1.241× | 1.091× | 8/9 | 0 | 1.000× | 0.964× |
| batch16 | 1.062× | 0.933× | 4/9 | 5 | 1.217× | 1.126× |
| stream | 1.290× | 1.133× | 8/9 | 0 | 1.000× | 0.928× |
| pair_generic | 1.405× | 1.234× | 8/9 | 0 | 1.000× | 0.852× |
| direct | 1.438× | 1.264× | 9/9 | 0 | 1.000× | 0.832× |
| oracle | 1.196× | 1.051× | 5/9 | 0 | 1.000× | 1.000× |

| Isolated comparison | Cycle reduction | Range across eligible cases | What it establishes |
|---|---:|---:|---|
| E1 vs V0 | 5.03% | 0.74–8.31% | Removing redundant full-range clamps helps, especially in internal RAM and small maps. |
| E3 vs V0 | 5.60% | 1.02–11.02% | Specializing vertical height helps even with adjacent load/use pairs and clamps. |
| E2 vs E3 | 2.29% | 0.36–4.38% | Moving an independent instruction into the load-use gap helps with the same specialized code shape and clamps. |
| E4 vs V0 | 15.96% | 2.46–26.74% | Removing the clamps also frees registers for additional independent loads. The effects should not be added arithmetically. |
| Circular vs prefix | 4.79% | −2.26% to +17.20% | The ring helps mainly on the three 5×5 cases. It ties or trails on the tested 3×3 streamer cases. |
| 128-channel vs 16-channel batches | 22.07% | 9.09–32.29% | Completing more groups per column is the larger material gain. This includes fewer leaf calls and more contiguous tensor accesses. |
| Paired SIMD vs stream | 22.54% | −0.01% to +48.38% | Preserving both histories in registers is most valuable for 32×32×32 in internal RAM. The largest reviewer case is roughly tied. |
| Direct vs generic driver, paired SIMD retained | 6.90% | 0.02–15.60% | The same leaf benefits from a specialized C row loop. The paired internal-RAM case went from 26,993 to 22,781 cycles. |

E4 still lost on four initial cases, including all three large reviewer cases. On 5×5 12×12×128, E4 alone was faster than the streaming variants. On the large 20×20×128 PSRAM case the streamer took 277,656 cycles versus 319,635 for E4 and 308,544 for master. That contrast is why the shortlist kept the no-ring E4 policy and the streaming alternatives for separate evaluation.

[Raw initial captures and per-boot values](logs/initial)

## Shortlist on all 64 configurations

Each of the five extended boots passed 104 cases, including all 64 shape-and-memory combinations for each of eight timed modes. This is a fresh comparison with rotating order and a different candidate set from the archived finalist study, which reported 62/64 for the complete finalist. The full-sweep build used the same sdkconfig as the initial build, and all 11 normalized pooling compilation commands matched. [Compiler settings](logs/compile-settings.txt)

First variant per boot was master, v0, v0_policy, e4_policy, e4.

| Shape | Memory | master | v0 | v0_policy | e4_policy | e4 | stream | five_policy | direct |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 3×3, 16×16×16 | Internal RAM | 11,954 | 7,381 | 7,451 | 5,733 | 5,659 | 7,390 | 7,461 | 7,390 |
| 3×3, 16×16×16 | PSRAM | 13,087 | 7,381 | 7,437 | 5,719 | 5,659 | 7,390 | 7,447 | 7,390 |
| 5×5, 6×6×128 | PSRAM | 12,837 | 10,828 | 10,878 | 8,652 | 8,598 | 8,125 | 8,114 | 8,116 |
| 5×5, 12×12×128 | PSRAM | 53,790 | 39,946 | 39,994 | 30,423 | 30,369 | 32,897 | 32,886 | 32,888 |
| 5×5, 20×20×128 | PSRAM | 308,641 | 340,079 | 308,734 | 308,734 | 319,743 | 277,744 | 277,744 | 277,744 |
| 3×3, 32×32×64 | PSRAM | 378,948 | 442,721 | 378,957 | 378,957 | 421,694 | 372,940 | 378,957 | 372,940 |
| 3×3, 56×56×32 | PSRAM | 836,646 | 904,069 | 836,814 | 836,814 | 881,817 | 836,650 | 836,814 | 836,639 |

| Mode | Geomean speedup vs master | Geomean speedup vs V0 | Wins vs master | Losses >1% | Worst vs master | Geomean cycles / oracle |
|---|---:|---:|---:|---:|---:|---:|
| master | 1.000× | 0.802× | 0/64 | 0 | 1.000× | 1.310× |
| v0 | 1.247× | 1.000× | 37/64 | 27 | 1.263× | 1.051× |
| v0_policy | 1.302× | 1.044× | 35/64 | 1 | 1.011× | 1.007× |
| e4_policy | 1.465× | 1.175× | 35/64 | 1 | 1.011× | 0.895× |
| e4 | 1.499× | 1.203× | 47/64 | 17 | 1.146× | 0.874× |
| stream | 1.442× | 1.157× | 62/64 | 1 | 1.018× | 0.909× |
| five_policy | 1.397× | 1.121× | 38/64 | 1 | 1.011× | 0.938× |
| direct | 1.464× | 1.174× | 63/64 | 1 | 1.018× | 0.895× |
| oracle | 1.310× | 1.051× | 37/64 | 0 | 1.000× | 1.000× |

| Shape | Memory | Mode | Master | Median | Median / master |
|---|---|---|---:|---:|---:|
| 3×3, 8×64×64 | PSRAM | e4 | 126,832 | 132,895 | 1.048× |
| 3×3, 16×16×128 | PSRAM | e4 | 111,952 | 125,868 | 1.124× |
| 3×3, 16×24×128 | PSRAM | e4 | 227,248 | 253,100 | 1.114× |
| 3×3, 16×32×64 | PSRAM | e4 | 127,409 | 141,290 | 1.109× |
| 5×5, 20×20×128 | PSRAM | e4 | 308,641 | 319,743 | 1.036× |
| 3×3, 32×8×64 | Internal RAM | v0_policy | 24,730 | 24,994 | 1.011× |
| 3×3, 32×8×64 | Internal RAM | e4_policy | 24,730 | 24,994 | 1.011× |
| 3×3, 32×8×64 | Internal RAM | five_policy | 24,730 | 24,993 | 1.011× |
| 3×3, 32×16×64 | PSRAM | e4 | 112,469 | 128,837 | 1.146× |
| 3×3, 32×24×64 | PSRAM | e4 | 224,921 | 253,031 | 1.125× |
| 3×3, 32×32×32 | PSRAM | e4 | 127,010 | 132,119 | 1.040× |
| 3×3, 32×32×48 | PSRAM | e4 | 228,935 | 249,242 | 1.089× |
| 3×3, 32×32×64 | PSRAM | e4 | 378,948 | 421,694 | 1.113× |
| 3×3, 32×64×64 | PSRAM | e4 | 1,071,390 | 1,159,016 | 1.082× |
| 3×3, 56×56×32 | PSRAM | e4 | 836,646 | 881,817 | 1.054× |
| 3×3, 64×8×64 | PSRAM | e4 | 123,286 | 139,402 | 1.131× |
| 3×3, 64×32×64 | PSRAM | e4 | 1,071,393 | 1,167,294 | 1.090× |
| 3×3, 128×16×64 | PSRAM | e4 | 1,070,232 | 1,169,993 | 1.093× |
| 3×3, 256×8×64 | PSRAM | e4 | 1,344,993 | 1,455,140 | 1.082× |
| 3×3, 256×8×64 | PSRAM | stream | 1,344,993 | 1,369,714 | 1.018× |
| 3×3, 256×8×64 | PSRAM | direct | 1,344,993 | 1,369,705 | 1.018× |
| 5×5, 256×8×64 | PSRAM | e4 | 6,515,895 | 7,275,858 | 1.117× |

The V0 fallback policy came within 0.7% of the pointwise master/V0 oracle in geometric-mean cycles. The same fixed policy with E4 reached 1.465× versus master, essentially equal to the complete finalist at 1.464×. E4 alone achieved a higher mean but had 17 losses above 1% and a worst case of 14.6% slower. E4 + fallback measured one greater-than-1% loss, 264 cycles (1.07%) on the internal-RAM 32×8×64 3×3 case. The corresponding policies reached near-master cycles on the large reviewer cases because their measured dispatch chose master there. On 20×20×128 PSRAM, full streaming retained a 10.0% win that those policies gave up.

The no-pair streamer won 62 of 64, one fewer than the complete finalist in this firmware, and used about 1.5% more cycles in the geometric mean. Both retained the approximately 1.84% wide-row loss on PSRAM at 256×8×64. Pairing still buys substantial shape-specific performance. In the matched initial benchmark, 32×32×32 internal RAM took 52,294 cycles with streaming and 22,781 with the direct paired path. Its value depends on the workload mix.

[Raw extended captures and exact cycle samples](logs/sweep)

## Recommendation

**Advance E4 with the measured fallback as the lowest-complexity option for review.** Keep full-range clamp elimination, fixed-height vertical reduction and the independent-load schedule. This candidate adds a 318-byte leaf beside V0 and needs no history array. It preserves the aggregate gain on this matrix. Omit the column history buffer, paired leaf and direct row driver if those shape-specific gains are secondary.

The threshold is fitted to earlier results on much of the same shape set. The full ablation establishes its behavior on this board, while performance on independent shapes, other cache configurations and other PSRAM placements remains open. Its worst loss narrowly exceeds the 1% review line. No measured simplification satisfies a strict zero-regression or 1% maximum-loss gate. If a threshold is undesirable, **retain the scheduled 128-channel circular streamer and drop the pair**. That retains more wins and the large 5×5 advantage at the cost of 512 bytes of local history. Keep the pair only if 32-channel 3×3 is important in the target workload.

[Source and memory costs](COMPLEXITY.md) · [Reproduction and policy definition](ABLATION.md)

## Correctness

All nine test modes passed 861 checks each, including 45 max-pool checks per mode, with the dual-core worker active and zero failures or skips. The banks covered the streamer and complete finalist, the three fallback policies, and the four individual instruction-level controls. All five boots of both benchmark stages passed ANSI equality, output guards and allocation audits for every reported variant. [Test validation](logs/correctness.txt) · [Streamer and finalist](logs/tests-0) · [Policies](logs/tests-1) · [Instruction controls](logs/tests-2)
