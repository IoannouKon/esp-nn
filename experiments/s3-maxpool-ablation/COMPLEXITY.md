# Complexity and memory cost

The table counts physical source lines, including comments and blanks, and reports code bytes per linked assembly leaf from the initial benchmark ELF. It separates shared macro source from the bytes instantiated for each variant. All ablation-only code lives in the benchmark patch; the normal branch implementation remains the inherited kernel-only finalist. [ELF symbols](logs/symbol-sizes.txt) · [GCC stack report](logs/stack-usage.su) · [Harness source](ablation-harness.patch)

| Optimization | C and assembly source footprint | Compiled leaf bytes | Active stack and history | Complexity |
|---|---|---:|---|---|
| E0 | Original PR added 33 C and 66 assembly lines over master | 176 | 304 B, 0 B history array | One generic vertical loop and one leaf call per row/group. |
| E1 | Three-line dispatch arm and one instantiation of the shared macro block. Clamp-free store replaces two vector operations and the leaf omits four bounds-setup instructions. | 131 | 304 B, 0 B array | Low. Full-range gate must still retain the clamped path. |
| E2 | Three-line arm; scheduling branch is shared with E3. It moves one ALU instruction and uses the same row-count cases. | 414 | 304 B, 0 B array | Low scheduling change, moderate fixed-block maintenance. |
| E3 | Three-line arm and five specialized row-count instantiations; same shared block. | 414 | 304 B, 0 B array | Moderate. Border and interior heights must agree with wrapper clipping. |
| E4 | Three-line arm and one instantiation, using both clamp elimination and the independent-load branch of the common block. | 318 | 304 B, 0 B array | Moderate. Frees q6/q7 under a full-range invariant. |
| E5 prefix | Uses the shared column driver. One explicit C leaf-selection line; shared stream assembly file delta is +74/−18 lines for both representations, including common macro refactoring. | 1,036 | 1,056 B, 512 B reserved history | High. Multiple dependent prefix updates and stores per channel group. |
| E6 stream and batching | Clean counterpart has a 21-line C streaming helper and 148 assembly lines, plus shared private offsets and dispatch. The 16-channel batch control changes one C limit and shares the same assembly. | 1,026 | 1,056 B in the measured driver, 512 B reserved history | Moderate to high. Raw aligned ring and slot arithmetic, fewer state writes. |
| E7 paired SIMD | 67 paired assembly lines in the kernel-only diff, and shared generic traversal in the experiment. | 267 | 496 B, 0 B array on the paired route | Moderate. Eight-register schedule precisely fits two 3×3 histories. |
| E8 direct driver | 16 C lines in the cleaned pair helper. The measured leaf is the same as E7. | 267 shared | 496 B, 0 B array in the measured driver | Low incremental. Explicit first, interior and last rows avoid the generic tile/group dispatch. |
| E9 clean finalist | 64 C, 216 assembly, 8 private-header lines added to the original PR | 1,022 stream + 253 pair | 896 B streaming with 512 B history; 368 B paired; 304 B on V0 | Highest total source and validation cost. Maintains two separate new leaves and the original clamped leaf. |

The E1–E4 assembly shares one 137-line addition including documentation, macro conditionals and the four instantiation statements. Keeping a single variant only requires the selected branches of the macro block, so the source count is not multiplied by four. The normal narrow-clamp fallback requires the existing 176-byte leaf. The figures for E1–E4 therefore represent additional emitted text when added beside V0, not the net size of replacing V0. The streaming/pair symbols are likewise incremental when added beside V0. Linker alignment and the C wrapper are excluded from per-leaf text. The linked experiment's common C selector, column helper and public wrapper occupy 891, 175 and 1,812 bytes, respectively, and include unrelated modes that a production extraction would remove.

The measured paths use a 240 B public wrapper; the row-per-group leaves add 64 B. Streaming adds a 192 B research dispatcher, a 560 B C frame containing the history array, and a 64 B leaf. Paired processing avoids the column helper and its array. The clean production-shaped counterpart removes the research dispatcher. No new path uses heap storage. Prefix and circular history hold four 128-byte aligned planes, of which 3×3 uses only two. A stack placed in PSRAM would move the history there and change its performance.

## Simplified policies

| Candidate | Code and memory to retain | Architectural dependency |
|---|---|---|
| V0 + fallback | Existing V0 and upstream code, plus the common threshold predicate and dispatch | Relies on cache/shape policy calibration rather than extra SIMD machinery. |
| E4 + fallback | Add the 318-byte E4 leaf and its mode gate to the former candidate | No ring. Uses spare registers available only at full activation range. |
| Stream without pair | Retain the common streaming dispatch, C ring helper and 1,026-byte stream leaf | Still has local history. Avoids the paired leaf and orthogonal pair-driver logic. |
| 5×5 stream + V0 3×3 + fallback | Retain the stream, V0 and threshold route for 3×3. A dedicated extraction could omit the 3×3 stream instantiations. | 5×5 needs four history planes. Uses the original 3×3 clamped path or master. |
| Finalist | Both leaves and drivers, alongside V0 | Requires both the ring for larger SIMD batches and the register-fit dispatch for paired 3×3. |

The threshold predicate occupies 10 C lines, and policy evaluation plus remapping occupies 13 C lines in the common experimental wrapper. The master helper is a benchmark link-time alias of the existing upstream path; a production implementation can reuse the existing path in-place. The measured policy can nest the experimental public wrapper inside another 240 B master wrapper, with 32 B upstream assembly leaf frames and an optional 32 B band frame. This extra stack is specific to the experimental routing shape. The oracle has zero code, stack or dispatch only because it is a pointwise numerical comparison.
