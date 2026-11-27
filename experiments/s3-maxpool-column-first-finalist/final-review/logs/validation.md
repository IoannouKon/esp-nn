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
