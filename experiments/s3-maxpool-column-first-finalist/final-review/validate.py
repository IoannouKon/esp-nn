#!/usr/bin/env python3
"""Verify and tabulate the kernel-only patch's separate board validation."""
from pathlib import Path
import re
from statistics import median
import sys

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root.parent))
from analyze import REVIEW, read_boot, require, row_name
from summarize_controls import PLACEMENT, STANDALONE

logs = root / "logs"
test_path = logs / "test_app-1.log"
test = read_boot(test_path, logs / "test_app.sha256")
require("DUAL_CORE: active" in test and "TEST_RESULT: PASS" in test
        and "TEST_SUMMARY: passed=861, failed=0, skipped=0" in test
        and "TEST: max_pool_s8, passed=45, failed=0, skipped=0" in test,
        "Production diff failed its dual-core test suite")

review = [(tuple(fields), master, v0)
          for *fields, master, v0 in REVIEW]
expected = {shape for shape, _, _ in review} | {
    (32, 24, 64, 3, "ext"),
    (256, 8, 64, 3, "ext"),
}
valid = []
allocations = []
for i in range(1, 6):
    path = logs / f"bench_app-{i}.log"
    bench = read_boot(path, logs / "bench_app.sha256")
    require("BENCH_DONE cases=49 failures=0 skipped=0" in bench, f"{path}: benchmark totals")
    records = STANDALONE.findall(bench)
    output = {(int(w), int(h), int(c), int(f), mem): int(cycles)
              for mem, cycles, w, h, c, f in records}
    require(len(records) == len(expected) and output.keys() == expected,
            f"{path}: incomplete cycle or guard checks")
    placement = {}
    for direction, mem, size, fields, w, h, c, f in PLACEMENT.findall(bench):
        shape = int(w), int(h), int(c), int(f), mem
        pointers = tuple(int(p, 16) for p in re.findall(r"=0x([0-9a-f]+)", fields))
        require(int(size) == int(w)*int(h)*int(c)
                and len(pointers) == (2 if direction == "INPUT" else 3)
                and all(p % 16 == 0 for p in pointers)
                and (shape, direction) not in placement, f"{path}: placement audit {shape}")
        placement[shape, direction] = pointers
    require(placement.keys() == {(s, d) for s in expected for d in ("INPUT", "OUTPUT")},
            f"{path}: incomplete placement audit")
    allocations.append(placement)
    valid.append(output)
require(all(p == allocations[0] for p in allocations), "Addresses differ across validation boots")
require((logs / "bench_app.sdkconfig").read_bytes() ==
        (root.parent / "reference/config/master-bench_app.sdkconfig").read_bytes(),
        "Validation sdkconfig differs from the archived baseline")

print("The kernel-only patch passed 861 dual-core checks (45 max-pool), with zero failures or skips.")
print("The five board boots each passed 49 benchmark cases, including the nine audited max-pool shapes.")
print("\n| Shape | Memory | Kernel-only patch median | Boot samples | Archived master for reviewer cases |")
print("|---|---|---:|---|---:|")
for shape, master, _ in review + [((32, 24, 64, 3, "ext"), None, None), ((256, 8, 64, 3, "ext"), None, None)]:
    samples = [boot[shape] for boot in valid]
    baseline = f"{master:,}" if master is not None else "—"
    print(f"| {row_name(shape)} | {median(samples):,} | {' / '.join(map(str, samples))} | {baseline} |")
