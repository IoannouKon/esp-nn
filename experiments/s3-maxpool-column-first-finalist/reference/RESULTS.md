# ESP-NN PR #68 benchmark reproduction

Reproduced **4/4 reported wins** and **3/3 reported regressions**. All seven cases passed the bit-exact ANSI comparison and output guard checks on both implementations across all five boots.

| Filter | Input shape | Memory | Reviewer master | Local master | Reviewer PR | Local PR | Local PR/master | Speedup | Correctness |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| 3×3 | 16×16×16 | Internal RAM | 11,954 | 11,954 | 7,239 | 7,239 | 0.606 | 1.651× | Pass |
| 3×3 | 16×16×16 | PSRAM | 13,087 | 13,087 | 7,239 | 7,239 | 0.553 | 1.808× | Pass |
| 5×5 | 6×6×128 | PSRAM | 12,837 | 12,837 | 10,460 | 10,748 | 0.837 | 1.194× | Pass |
| 5×5 | 12×12×128 | PSRAM | 53,685 | 54,267 | 38,576 | 40,069 | 0.738 | 1.354× | Pass |
| 5×5 | 20×20×128 | PSRAM | 306,730 | 305,809 | 335,668 | 337,848 | 1.105 | 0.905× | Pass |
| 3×3 | 32×32×64 | PSRAM | 377,619 | 379,449 | 441,702 | 443,358 | 1.168 | 0.856× | Pass |
| 3×3 | 56×56×32 | PSRAM | 836,646 | 836,649 | 903,836 | 903,836 | 1.080 | 0.926× | Pass |

## Percentage deviation

Signed deviation is 100 × (local / reviewer − 1). Local PR change is 100 × (PR / master − 1).

| Filter | Input shape | Memory | Master deviation | PR deviation | Local PR change vs. master |
|---|---|---|---:|---:|---:|
| 3×3 | 16×16×16 | Internal RAM | +0.00% | +0.00% | -39.44% |
| 3×3 | 16×16×16 | PSRAM | +0.00% | +0.00% | -44.69% |
| 5×5 | 6×6×128 | PSRAM | +0.00% | +2.75% | -16.27% |
| 5×5 | 12×12×128 | PSRAM | +1.08% | +3.87% | -26.16% |
| 5×5 | 20×20×128 | PSRAM | -0.30% | +0.65% | +10.48% |
| 3×3 | 32×32×64 | PSRAM | +0.48% | +0.37% | +16.84% |
| 3×3 | 56×56×32 | PSRAM | +0.00% | +0.00% | +8.03% |

## Per-boot timings

| Filter | Input shape | Memory | Master samples | PR samples |
|---|---|---|---|---|
| 3×3 | 16×16×16 | Internal RAM | 11954 / 11954 / 11954 / 11954 / 11954 | 7239 / 7239 / 7239 / 7239 / 7239 |
| 3×3 | 16×16×16 | PSRAM | 13087 / 13087 / 13087 / 13087 / 13087 | 7239 / 7239 / 7239 / 7239 / 7239 |
| 5×5 | 6×6×128 | PSRAM | 12837 / 12837 / 12837 / 12837 / 12837 | 10748 / 10748 / 10748 / 10748 / 10748 |
| 5×5 | 12×12×128 | PSRAM | 54267 / 54267 / 54267 / 54267 / 54267 | 40069 / 40069 / 40069 / 40069 / 40069 |
| 5×5 | 20×20×128 | PSRAM | 305809 / 305809 / 305809 / 305809 / 305809 | 337848 / 337848 / 337848 / 337848 / 337848 |
| 3×3 | 32×32×64 | PSRAM | 379449 / 379449 / 379449 / 379449 / 379449 | 443358 / 443358 / 443358 / 443358 / 443358 |
| 3×3 | 56×56×32 | PSRAM | 836649 / 836649 / 836649 / 836649 / 836649 | 903836 / 903836 / 903836 / 903836 / 903836 |

## Correctness and configuration checks

- **master** test_app passed 849 checks, including 33 max-pool and 247 dual-core checks, with zero failures or skips.
- **pr** test_app passed 853 checks, including 37 max-pool and 247 dual-core checks, with zero failures or skips.
- All max-pool inputs and timed outputs passed the placement and 16-byte alignment checks. ANSI reference buffers were in internal DRAM. No allocation failures occurred.
- All audited input, output and reference buffer addresses matched across the ten boots.
- Corresponding builds used byte-identical sdkconfigs, 1,012 matching benchmark compiler commands and 1,016 matching test compiler commands after normalizing checkout paths.
- The runtime cache readout was POOL_CACHE ictrl=0xb dctrl=0x15 icache_kib=16 icache_ways=8 icache_line=32 dcache_kib=64 dcache_ways_config=8 dcache_line=64 psram_mhz_config=80.
- The final captures contained all 70 output-audit records. The USB console omitted 0 ordinary MaxPool rows, and every received ordinary row matched its audit record.

## Hardware and software

| Item | Local setting |
|---|---|
| Board | ESP32-S3-EYE, ESP32-S3 chip revision v0.2, USB-Serial/JTAG |
| CPU | 240 MHz, FreeRTOS dual core enabled, benchmark task pinned to core 0 |
| Instruction cache | 16 KiB, 8-way, 32-byte cache lines |
| Data cache | 64 KiB, 8-way, 64-byte cache lines |
| PSRAM | 8 MiB, octal, 80 MHz, capability allocator |
| SPI flash | 8 MiB, DIO at 80 MHz |
| ESP-IDF | Official v6.1 tag, fff9895c82d744c7237be8847347bdd1b07c6643 |
| Compiler | Xtensa GCC 15.2.0, crosstool-NG esp-15.2.0_20251204. ESP-NN max-pool objects have -O2 as the final optimization flag. The benchmark harness has -Og. |
| Master kernel | 9fd985a931a69ef15a3d9e151f46261a36d51581 |
| PR kernel | dafea5932861701ac79c7830a29b487442e50cc6, including the stack-frame fix |

Cache sizes and line sizes were read from the live control registers and ROM APIs. Instruction cache associativity came from the hardware register. Data cache associativity came from the generated configuration used by the ESP-IDF startup call that programs DCache. The boot logs confirm the CPU and PSRAM settings.

## Procedure and differences from the review

All seven MaxPool shapes used INT8, stride 1, SAME padding and activation limits [-128, 127]. The two builds used the same upstream seed, inputs and buffer placement. The measurements use five master/PR pairs on the same board. Each boot reports the minimum of eight timed calls following one warm-up, using upstream's alternating inputs and interrupt masking. The reported cycles are the median of those five minima.

Vikram reported ESP-IDF v6.1, 240 MHz and octal PSRAM. The review does not specify the exact IDF revision, compiler build, sdkconfig, cache geometry or PSRAM frequency for the reviewer’s board. The review was attached to 2d8d0ca, the PR commit immediately before the stack-frame fix, and this run used the requested fixed tip. [Reviewer measurements](https://github.com/espressif/esp-nn/pull/68#pullrequestreview-6086711789)

The initial serial captures omitted the ordinary MaxPool timing line for 12×12×128 on every benchmark boot. Those captures are archived. The final series repeated all five pairs after adding the timing and correctness fields to the output audit, outside the timed code. The harness ran all 47 cases on each final boot with zero failures or skips. The five added shapes ran only MaxPool. The kernel sources came directly from the two pinned commits.

## Evidence and reproduction

[Serial logs](logs/runs) · [Board configurations](config) · [Reproduction instructions](../REPRODUCE.md)
