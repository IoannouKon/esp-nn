#!/usr/bin/env python3
"""Check all published dual-core test-bank captures."""
from pathlib import Path
import re
import sys

root = Path(__file__).resolve().parent
sys.path.insert(0, str(root.parent / "s3-maxpool-column-first-finalist"))
from analyze import read_boot, require

expected = ((13, 15), (24, 25, 26), (16, 17, 18, 19))
logs = Path(sys.argv[1]) if len(sys.argv) > 1 else root / "logs"
for bank, modes in enumerate(expected):
    path = logs / f"tests-{bank}" / "run-1.log"
    text = read_boot(path)
    require(f"ABLATION_TEST_BANK: {bank}" in text and "TEST_RESULT: PASS" in text,
            f"{path}: failed or wrong test bank")
    require(text.count("DUAL_CORE: active") == len(modes), f"{path}: dual-core status")
    done = re.findall(r"^MODE_DONE (\d+) passed=(\d+) failed=(\d+) skipped=(\d+)$", text, re.M)
    require(done == [(str(mode), "861", "0", "0") for mode in modes], f"{path}: {done}")
    require(text.count("TEST: max_pool_s8, passed=45, failed=0, skipped=0") == len(modes),
            f"{path}: MaxPool suite")
    print(f"Bank {bank}: modes {', '.join(map(str, modes))} passed 861 checks each.")
