# ESP32-S3 MaxPool optimization ablation

This experiment branches from finalist commit 3edad4fcaac28ae8a4c49e97b56e0894abe82055. The inherited production-shaped finalist remains the default implementation on this branch. The separate benchmark patch instantiates the controls in a detached checkout of PR tip dafea59. Master is 9fd985a, with its original MaxPool wrapper linked under an alternate name and the common upstream assembly shared. [Prior investigation](../s3-maxpool-column-first-finalist/INVESTIGATION.md)

## Comparisons

| Experiment | Timed labels | Controlled change |
|---|---|---|
| E0 | v0 | Current PR row-per-channel-group loop, clamp and register-resident prefix history. |
| E1 | v0 → e1 | Remove the two output clamp instructions and the activation-bounds loads for full INT8 range. Preserve V0 traversal, dynamic vertical loop and history. |
| E2 | e3 → e2; v0 → e2 as a combined control | Keep both clamp vectors live. Move the horizontal pointer increment into the first load-use gap in the specialized vertical sequence. Compare E2 against E3 to isolate scheduling. |
| E3 | v0 → e3 | Specialize the valid input-row count (two or three for 3×3; three through five for 5×5). Keep adjacent load/use ordering, V0 traversal, history and clamps. |
| E4 | v0 → e4 | Combine specialization, full-range clamp elimination and a wider schedule using the freed q6/q7 as temporary load vectors. |
| E5 | prefix → stream | Use the same column-first traversal, 128-channel batching, full-range gate and scheduled vertical loads. Switch from updating prefix vectors to overwriting one raw-column ring slot. |
| E6 | batch16 → stream; e4 → stream as a combined control | Compare the same ring and assembly leaf with one versus up to eight groups in a batch. E4 versus streaming also changes memory order, stored history and the row driver. |
| E7 | stream → pair_generic | Replace the stream with two register-resident histories for eligible 32-channel 3×3. Filter, activation and input remain the same. |
| E8 | pair_generic → direct | Use the same paired leaf and whole-row launch. Replace generic row/column/group traversal in C with a direct first/interior/last row driver. |
| E9 | direct | The complete finalist from the earlier study. |

E2 uses fixed-height vertical blocks, so the instruction reorder can be measured without adding a new dynamic pipeline or changing the register budget. E2 versus E0 includes specialization as well. E4 schedules more vertical loads because omitting clamps frees two SIMD registers. Column-first processing across groups needs separate live histories; the paired leaf can keep two 3×3 histories in the eight SIMD registers, while more groups or 5×5 need memory or recomputation. Consequently the transition from V0 to streaming does not isolate traversal from history. E5 keeps the vertical code shared. Prefix and ring seeding and right-border reductions necessarily differ because their states represent different quantities.

The paired comparisons use 56×56×32 in PSRAM plus 32×32×32 in internal RAM and PSRAM. E7 and E8 have no paired semantics on other shapes. Both protected the 64-byte leaf frame and the original fallback/clamping gates. Policy candidates are tested through the normal experimental public entry point.

## Measured policy and theoretical reference

The policy was fixed before the new runs using the previous V0 measurements. For an eligible full-range 3×3 case, use master if C ≥ 64 and tensor bytes ≥ 16,384, or if input is in PSRAM, C ≥ 32 and tensor bytes ≥ 32,768. For 5×5, use master if input is in PSRAM, C ≥ 64 and tensor bytes ≥ 49,152. The V0 and E4 policy candidates use the same rule. The 5×5-only streaming hybrid uses the 3×3 rule with V0 and keeps streaming on 5×5. The measured rule performs its own pointer-region and shape checks within the timed public call. The thresholds are derived from earlier measurements on much of the same shape set, so the sweep measures repeatability and fit on that set. Independent-shape generalization remains unverified.

The oracle takes min(master median, V0 median) independently for each case. It is an analytical reference with no dispatch cost or constraint on how the winner is selected. It does not represent an implemented policy. Speedups are equally weighted geometric means of the per-case cycle ratios. A loss above 1% is flagged for review, while the tables also retain smaller gaps.

## Protocol

ESP32-S3-EYE, ESP-IDF v6.1 at fff9895c82d744c7237be8847347bdd1b07c6643, Xtensa GCC 15.2.0, 240 MHz, octal PSRAM at 80 MHz and 64 KiB eight-way DCache with 64-byte lines. The extended build uses the previous sweep's watchdog and long-reference settings. Within each boot variants run consecutively against the same pair of seeded inputs, output allocation and ANSI gold buffers. The benchmark rotates which variant goes first when the RTC order counter is retained, and logs that order. All timings use the stock minimum of eight timed calls after one warm-up. Results are medians across five verified resets. Guard checks run for the timed invocations and separate counter samples, with identical memory-placement auditing. [SDK and baseline provenance](../s3-maxpool-column-first-finalist/REPRODUCE.md)

The inherited captures establish the original finalist comparisons and provide the policy training measurements. The existing full-matrix timings are not substituted for any of the new matched ablations.

## Reproduction

Source export.sh from the pinned ESP-IDF checkout. From this directory:

    scratch="$(mktemp -d)"
    ./reproduce.sh initial "$scratch"
    python3 report.py "$scratch/logs/initial" initial
    ./reproduce.sh sweep "$scratch"
    python3 report.py "$scratch/logs/sweep" sweep
    for bank in 0 1 2; do
        ./reproduce.sh "tests-$bank" "$scratch"
    done

The optional final argument to reproduce.sh is the board serial device. The script applies [the ablation harness patch](ablation-harness.patch) to a detached original-PR checkout in the scratch area. Separate firmware builds fix each correctness bank to avoid exhausting the upstream test process after too many suites in one boot. The experimental selection global and benchmark harness are for serial runs on the test board.

After the test runs, verify all nine complete dual-core suites with:

    python3 verify_tests.py "$scratch/logs"
