# ESP32-S3 DCache controls

Each configuration below is a single-boot diagnostic. The default configuration also has a separate five-boot matrix. Each cycle count is the upstream in-boot minimum. PSRAM misses come from the separate warmed profiling call. The 32 KiB and 32-byte-line firmware were built from an earlier benchmark snapshot. The master, V0 and reviewer-case timing loops use the same source paths, but changes to the benchmark telemetry and linked image can affect absolute PSRAM cycles. Interpret the large changes and within-image rankings as diagnostics.

### candidate64

POOL_CACHE ictrl=0xb dctrl=0x15 icache_kib=16 icache_ways=8 icache_line=32 dcache_kib=64 dcache_ways_config=8 dcache_line=64 psram_mhz_config=80

| Shape | Memory | Master cycles | V0 cycles | V0/master | Master PSRAM misses | V0 PSRAM misses |
|---|---|---:|---:|---:|---:|---:|
| 3×3, 16×16×16 | Internal RAM | 11,954 | 7,252 | 0.607 | 0 | 0 |
| 3×3, 16×16×16 | PSRAM | 13,087 | 7,252 | 0.554 | 0 | 0 |
| 5×5, 6×6×128 | PSRAM | 12,837 | 10,761 | 0.838 | 0 | 0 |
| 5×5, 12×12×128 | PSRAM | 53,685 | 39,741 | 0.740 | 0 | 0 |
| 5×5, 20×20×128 | PSRAM | 307,457 | 341,093 | 1.109 | 1,017 | 1,012 |
| 3×3, 32×32×64 | PSRAM | 377,208 | 440,952 | 1.169 | 1,301 | 1,301 |
| 3×3, 56×56×32 | PSRAM | 836,646 | 903,839 | 1.080 | 3,139 | 3,139 |

### control32-64

POOL_CACHE ictrl=0xb dctrl=0x11 icache_kib=16 icache_ways=8 icache_line=32 dcache_kib=32 dcache_ways_config=8 dcache_line=64 psram_mhz_config=80

| Shape | Memory | Master cycles | V0 cycles | V0/master | Master PSRAM misses | V0 PSRAM misses |
|---|---|---:|---:|---:|---:|---:|
| 3×3, 16×16×16 | Internal RAM | 11,954 | 7,253 | 0.607 | 0 | 0 |
| 3×3, 16×16×16 | PSRAM | 13,087 | 7,253 | 0.554 | 0 | 0 |
| 5×5, 6×6×128 | PSRAM | 12,837 | 10,762 | 0.838 | 0 | 0 |
| 5×5, 12×12×128 | PSRAM | 101,233 | 100,094 | 0.989 | 182 | 189 |
| 5×5, 20×20×128 | PSRAM | 435,831 | 482,396 | 1.107 | 1,604 | 1,604 |
| 3×3, 32×32×64 | PSRAM | 535,995 | 600,958 | 1.121 | 2,051 | 2,051 |
| 3×3, 56×56×32 | PSRAM | 800,847 | 868,502 | 1.084 | 3,140 | 3,140 |

### control64-32

POOL_CACHE ictrl=0xb dctrl=0xd icache_kib=16 icache_ways=8 icache_line=32 dcache_kib=64 dcache_ways_config=8 dcache_line=32 psram_mhz_config=80

| Shape | Memory | Master cycles | V0 cycles | V0/master | Master PSRAM misses | V0 PSRAM misses |
|---|---|---:|---:|---:|---:|---:|
| 3×3, 16×16×16 | Internal RAM | 11,954 | 7,252 | 0.607 | 0 | 0 |
| 3×3, 16×16×16 | PSRAM | 13,087 | 7,252 | 0.554 | 0 | 0 |
| 5×5, 6×6×128 | PSRAM | 12,837 | 10,761 | 0.838 | 0 | 0 |
| 5×5, 12×12×128 | PSRAM | 53,784 | 39,841 | 0.741 | 0 | 0 |
| 5×5, 20×20×128 | PSRAM | 440,697 | 430,557 | 0.977 | 2,020 | 2,011 |
| 3×3, 32×32×64 | PSRAM | 521,952 | 564,357 | 1.081 | 2,588 | 2,588 |
| 3×3, 56×56×32 | PSRAM | 1,171,486 | 1,266,339 | 1.081 | 6,275 | 6,275 |

### control64-4way

POOL_CACHE ictrl=0xb dctrl=0x15 icache_kib=16 icache_ways=8 icache_line=32 dcache_kib=64 dcache_ways_config=4 dcache_line=64 psram_mhz_config=80

| Shape | Memory | Master cycles | V0 cycles | V0/master | Master PSRAM misses | V0 PSRAM misses |
|---|---|---:|---:|---:|---:|---:|
| 3×3, 16×16×16 | Internal RAM | 11,954 | 7,252 | 0.607 | 0 | 0 |
| 3×3, 16×16×16 | PSRAM | 13,087 | 7,252 | 0.554 | 0 | 0 |
| 5×5, 6×6×128 | PSRAM | 12,837 | 10,761 | 0.838 | 0 | 0 |
| 5×5, 12×12×128 | PSRAM | 53,685 | 39,741 | 0.740 | 0 | 0 |
| 5×5, 20×20×128 | PSRAM | 307,457 | 341,053 | 1.109 | 1,017 | 1,012 |
| 3×3, 32×32×64 | PSRAM | 377,205 | 440,952 | 1.169 | 1,301 | 1,301 |
| 3×3, 56×56×32 | PSRAM | 836,646 | 903,839 | 1.080 | 3,139 | 3,139 |

[Default raw capture](logs/candidate64/run-1.log) · [32 KiB](logs/control32-64/run-1.log) · [32-byte lines](logs/control64-32/run-1.log) · [Four ways](logs/control64-4way/run-1.log)
