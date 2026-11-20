# ESP-NN extended benchmark (ESP32-S3-EYE) — Agent kit

**Status: Source package prepared, host sanity-checked, no ESP32-S3 measurements in this ZIP.**

The user previously measured EXP-MEAN and Opt2 on two official ESP-NN shapes each, but wants to determine if the improvements survive a **broader, reproducible** sweep.

## Contents

| Path | Purpose |
|---|---|
| `AGENT_PROMPT.md` | Full task for Codex or a hardware-connected coding agent |
| `templates/bench_extended_mean.c` | Complete benchmark case implementation using Espressif's public INT8 mean APIs |
| `templates/bench_extended_pool.c` | Complete benchmark case implementation using Espressif's public INT8 maxpool APIs |
| `SHAPES.json` | Fixed 90-shape manifest with intended optimization eligibility |
| `scripts/shape_manifest.py` | Deterministic manifest generator |
| `scripts/install_extended.py` | Apply experimental app-only changes to a **disposable** checkout |
| `scripts/run_all.sh` | Full worktree/build/flash/collect/compare orchestration |
| `scripts/capture_monitor.py` | Bounded ESP-IDF monitor serial capture |
| `scripts/compare_extended.py` | Strict log validation and CSV/JSON/Markdown report |
| `tests/test_kit.py` | Host tests for manifest, code installer and strict comparator |
| `results/` | Empty; filled only after board experiments |

## Two ground rules

1. No modifications to the actual optimized ESP-NN kernel sources or existing vendor timing harness. The experimental app calls the same `bench_run()` API as Espressif's official benchmark, with many more shapes.
2. No fabricated performance claims. To obtain real numbers, run the kit's scripts on the machine with the ESP32-S3-EYE, ESP-IDF, and serial access.

## One-line agent instruction

> Read `AGENT_PROMPT.md` and execute it. Use the attached ZIP's code as the extended benchmark, evaluate stock vs EXP-MEAN vs Opt2 on my ESP32-S3-EYE, and return `RESULTS.md`, full CSV, and all raw logs. Do not modify existing experiment branches or hide losing shapes.

## Expected worktree state after installation

Only these new/modified experimental benchmarking files are allowed:

- `bench_app/main/bench_main.c` — modified only to select the extended sweep
- `bench_app/main/CMakeLists.txt` — modified to add two benchmark translation units
- `bench_app/main/bench_extended_mean.c` — newly added
- `bench_app/main/bench_extended_pool.c` — newly added

The rest, including `bench_app/components/bench_harness/bench.c`, and every optimized source must stay byte-for-byte as their checked-out commits.

## Known limitations

- Some exact shapes are from the vendor's original benchmark, but most are newly added **experimental** shapes.
- Warm-cache, fastest-after-warmup numbers follow vendor semantics. PSRAM does not mean cold-cache.
- All tensors use the stock harness's 16-byte-aligned, disjoint allocations. Misalignment/in-place cases require separate tests.
- The run limit is 20 minutes **per firmware boot** for the 90-case sweep, excluding build/flash; the code does not impose a 20-minute ceiling on creating three builds.
- The `results/` folder intentionally contains no measured cycle numbers.
