# AI Agent Task — Extended ESP32-S3-EYE ESP-NN kernel benchmarks

## Objective

Execute an **unbiased, multi-shape** A/B comparison on the actual ESP32-S3-EYE board for two **separate** experiments:

- **EXP-MEAN QACC** vs stock ESP-NN v1.5.0, measuring INT8 mean reduction.
- **Opt2 sliding max-pooling** vs stock ESP-NN v1.5.0, measuring INT8 max pooling.

Do not merge both optimizations, update or edit the kernel algorithms, or claim an entire CNN speedup from these operator tests.

## Immutable Git commits and branches

| Build | Exact revision | Git branch it represents |
|---|---|---|
| Stock baseline | `ace42ac7721119cd543fc40ffe719e601fa8f20f` | ESP-NN v1.5.0 |
| EXP-MEAN | `4bfa49c64a932f700688c2007a01d8ea1fa102ac` | `experiment/s3-global-mean-qacc` |
| Opt2 | `edb003c6770491abb74766835f4c803b9d4f5a20` | `experiment/s3-max-pool-128`; implementation was committed at `255d96b...` |

Source repository: `https://github.com/IoannouKon/esp-nn`.

Use separate **detached worktrees**, each ending in `/esp-nn`, because ESP-IDF bench app resolves the repository as a local component. Do **not** checkout/modify, reset, amend or push any of the user's existing branches. Do not edit any kernel files. The `run_all.sh` driver creates separate disposable worktrees.

## Read the kit before executing

1. `README_START_HERE.md`
2. `SHAPES.json` (immutable full list: **42 mean + 48 max-pooling cases**, 90 total)
3. `scripts/install_extended.py`
4. `scripts/run_all.sh`
5. `scripts/compare_extended.py`

The kit uses the **original Espressif `bench_run()` harness** unchanged. Only the experimental app selection and extra shape definitions are installed. The stock vendor `bench_app/main/bench_pooling.c` and `bench_softmax_mean.c` must be left untouched. The existing 40-case official benchmark and its reports are separate and must not be overwritten.

## First: inspect the source and preserve fairness

Confirm original ESP-NN v1.5.0 and branch heads. Compare changed production kernel files between stock and each candidate. Confirm the exact SHA of the Git commits. Verify original `bench_app/components/bench_harness/bench.c` remains byte-identical in **all three worktrees**. Verify the shapes, seed, `BENCH_ITERS=9`, output guards, warm-up and interrupt control are identical. Verify ESP-IDF is the same installation/version for every build and CPU=240 MHz, octal PSRAM=80 MHz.

The new bench cases are **research extensions** to the vendor benchmark, not cases published by Espressif. Never call them "the official benchmark results"; call them an *extended shape sweep using the unchanged official harness*.

## Execute

The existing board is expected on `/dev/ttyACM0`. Activate your working ESP-IDF v5.5.1 environment; toolchain is the ESP32-S3 Xtensa compiler. If needed fetch the fork so all three SHAs exist locally. Select a NEW workspace directory that does not exist and will not be inside a Git worktree. Example:

```bash
source ~/esp_s3/esp-idf/export.sh
bash scripts/run_all.sh \
  --repo /home/kostis/Desktop/ESP-NN/esp-nn \
  --workspace /home/kostis/Desktop/ESP-NN/extended-shape-run-1 \
  --port /dev/ttyACM0
```

**The `--repo` path is an example; locate the actual local ESP-NN checkout.** If the board port differs, discover it safely. The script will not overwrite an existing workspace and will not modify branch HEADs.

The script:

1. Makes three detached, isolated worktrees with the stock, EXP-MEAN and Opt2 revisions.
2. Installs IDENTICAL experimental app/harness call sites and 90-case manifest in each.
3. Builds all three with identical `sdkconfig` and checks their SHA-256.
4. Flash/runs in order **stock → EXP-MEAN → Opt2 → stock → Opt2 → EXP-MEAN**.
5. Captures all six raw serial outputs from `BENCH_START` through `BENCH_DONE`.
6. Enforces a **1,200-second (20-minute) monitor deadline for each full sweep**; build/flash time is separate. If it expires, fail and preserve partial results; never silently remove cases to fit the deadline.
7. Runs strict CSV/JSON/Markdown analysis and refuses to compare incomplete, failed, skipped or mismatched shape logs.

If a build or monitor capture fails, inspect source and build logs and fix only **experimental benchmark wrapper issues**, not the optimization kernels. Any changes must be applied identically to all three builds, documented and reviewed before proceeding. Do not claim runs you did not complete.

## What the shape sweep covers

Mean: 42 shapes (31 QACC-eligible on aligned disjoint inputs; 11 scalar fallback) covering 1–4096+ spatial elements, C=8..256, aligned and irregular channel counts, internal RAM and PSRAM, 4095/4096 saturation boundary, and the two original official cases.

Max pooling: 48 shapes (32 Opt2-eligible; 16 fallback) covering 3×3/5×5 SAME stride-1, 2×2 stride-2, 3×3 stride-2, VALID cases, smaller-than-filter input dimensions, channel tails, channel multiples of 16, various spatial sizes and both memory types. Includes the two original official max-pool cases.

The suite allocates 16-byte-aligned **separate** input/output tensors using the vendor harness. It does not test deliberate misalignment or in-place overlap. Those require additional standalone safety tests, not disguised benchmark cases. Preserve existing test_app correctness coverage.

For every case, `bench_run()` compares bit-exact outputs against ANSI C and checks output guard bytes, with two deterministic input buffers per case. A wrong result is a **FAIL**, regardless of cycles.

## Verdict rules

Compare only **EXP-MEAN vs stock on the mean rows**, and **Opt2 vs stock on the max-pool rows**. Other operator rows are controls. Show every shape, including regressions and fallbacks, not only winners. The comparison script groups SIMD-eligible/fallback paths and internal/PSRAM cases.

For each shape:

- Speedup = stock optimized median cycles / candidate optimized median cycles.
- Cycle reduction = `(1 − candidate / stock) × 100%`.
- Aggregate: geometric mean of speedups over all eligible shapes, separately for internal and PSRAM; report #wins, #losses, worst shape.
- Treat >1% speedup as WIN, >1% slowdown as LOSS, differences within 1% as NEUTRAL (a reporting convention, **not** a statistical confidence interval).
- Preserve individual boot results and ranges to identify instability.
- If eligible cases lose, report them clearly; do not hide them behind an average.
- A fallback result similar to stock is expected and **is not an optimization win**.
- These are **kernel cycle benchmarks**. Do not claim a full-CNN speedup; full-model inference would require a different workload.

## Deliverables

Return `results/analysis/RESULTS.md`, `comparison.csv`, `comparison.json`, raw logs, commit IDs, toolchain version, target settings, compile and SDK checks. Include an honest PASS / MIXED / LOSS / INCONCLUSIVE verdict separately for EXP-MEAN and Opt2. Include elapsed times and note whether either hit the 20-minute cap.

**Final request:** Does each optimization generalize beyond the two original official shapes? Report its median speedup, geometric-mean eligible speedup, best/worst case, number of wins/losses, and concrete limitations. No cherry-picking, no new optimizations, no fabricated measurements, and no Git push unless explicitly requested.
