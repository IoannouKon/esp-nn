# Firmware sizes and reproducibility checks

Each group links its own immutable model bundle. Section sizes are from the archived timed ELF. Sizes between variants should be compared within one group.

| Group | Variant | Flash image | Δ vs stock | Flash text | Flash rodata | IRAM text | DRAM data | DRAM BSS |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| core | stock | 1117040 | +0 | 352994 | 701828 | 51839 | 8948 | 2200 |
| core | opt2 | 1117632 | +592 | 353646 | 701764 | 51839 | 8948 | 2200 |
| core | mean | 1117520 | +480 | 353530 | 701764 | 51839 | 8948 | 2200 |
| core | combined | 1118352 | +1312 | 354182 | 701956 | 51839 | 8948 | 2200 |
| mobiles | stock | 7656784 | +0 | 352986 | 7241572 | 51839 | 8948 | 2200 |
| mobiles | opt2 | 7657360 | +576 | 353638 | 7241508 | 51839 | 8948 | 2200 |
| mobiles | mean | 7657248 | +464 | 353522 | 7241508 | 51839 | 8948 | 2200 |
| mobiles | combined | 7658096 | +1312 | 354174 | 7241700 | 51839 | 8948 | 2200 |
| lite0 | stock | 6057920 | +0 | 352422 | 5643284 | 51839 | 8948 | 2200 |
| lite0 | opt2 | 6058512 | +592 | 353074 | 5643220 | 51839 | 8948 | 2200 |
| lite0 | mean | 6058400 | +480 | 352958 | 5643220 | 51839 | 8948 | 2200 |
| lite0 | combined | 6059248 | +1328 | 353610 | 5643412 | 51839 | 8948 | 2200 |

Each published row belongs to a group whose four SDK configs and app-source hashes match. The check verifies the complete model and input bytes are embedded in each binary. Linked symbols match the respective kernel variants and contain no diagnostic wrappers. Serial ELF fingerprints match the archived image whenever a capture has completed.
