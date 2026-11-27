#!/usr/bin/env python3
"""Report the reviewer-case confirmation, tests and independent cache controls."""
from pathlib import Path
import re
from statistics import median

from analyze import BASE, RECORD, REVIEW, SHAPE, ranking, read_boot, require, row_name, summarize

STANDALONE = re.compile(r'^POOL_OUTPUT mem=(int|ext) bytes=\d+ .+ guard=64 opt=(\d+) '
                        r'failures=0 result=ok shape="' + SHAPE + '"$', re.M)
PLACEMENT = re.compile(r'^POOL_(INPUT|OUTPUT) mem=(int|ext) bytes=(\d+) (.+) '
                       r'result=ok shape="' + SHAPE + '"$', re.M)
CONTROLS = ("candidate64", "control32-64", "control64-32", "control64-4way")


def standalone_boot(path, firmware_hash=None):
    text = read_boot(path, firmware_hash)
    require("BENCH_DONE cases=47 failures=0 skipped=0" in text, f"{path}: benchmark failure")
    found = STANDALONE.findall(text)
    outputs = {(int(w), int(h), int(c), int(f), mem): int(cycles)
               for mem, cycles, w, h, c, f in found}
    require(len(found) == len(outputs) == len(REVIEW), f"{path}: incorrect output audits")
    placement = {}
    for direction, mem, size, fields, w, h, c, f in PLACEMENT.findall(text):
        shape = int(w), int(h), int(c), int(f), mem
        addresses = tuple(int(a, 16) for a in re.findall(r"=0x([0-9a-f]+)", fields))
        require(int(size) == int(w) * int(h) * int(c) and all(a % 16 == 0 for a in addresses)
                and len(addresses) == (2 if direction == "INPUT" else 3)
                and (shape, direction) not in placement, f"{path}: incorrect tensor addresses")
        placement[shape, direction] = addresses
    require(placement.keys() == {(shape, d) for shape in outputs for d in ("INPUT", "OUTPUT")},
            f"{path}: incomplete tensor audit")
    return outputs, placement


def standalone(label="standalone64", mode="Fit0"):
    paths = [BASE / "logs" / label / f"run-{i}.log" for i in range(1, 6)]
    samples = [standalone_boot(path)[0] for path in paths]
    print(f"| Shape | Memory | Archived master | Archived PR | {mode} | Speedup vs master | {mode} change vs PR | {mode} samples |")
    print("|---|---|---:|---:|---:|---:|---:|---|")
    for *key, master, current in REVIEW:
        shape = tuple(key)
        boot_values = [sample[shape] for sample in samples]
        cycles = median(boot_values)
        print(f"| {row_name(shape)} | {master:,} | {current:,} | {cycles:,} | {master/cycles:.4f}× | "
              f"{100*(cycles/current-1):+.2f}% | {' / '.join(map(str, boot_values))} |")


def tests():
    if all((BASE / "logs" / f"tests-{i}" / "run-1.log").exists() for i in (0, 4)):
        groups = tuple((f"tests-{i}", i, i + 4) for i in range(0, 16, 4))
    else:
        groups = (("tests-final", 0, 8), ("tests-8", 8, 12), ("tests-12", 12, 16))
    totals = []
    for label, first, last in groups:
        path = BASE / "logs" / label / "run-1.log"
        text = read_boot(path)
        require("Multicore app" in text, f"{path}: dual-core startup")
        if label != "tests-final":
            require("TEST_RESULT: PASS" in text, f"{path}: complete suite")
        matches = re.findall(r"^MODE_START (\d+)$(.*?)^MODE_DONE \1 passed=(\d+) failed=(\d+) skipped=(\d+)$",
                             text, re.M | re.S)
        valid = [(int(mode), n, f, s, suite) for mode, suite, n, f, s in matches if first <= int(mode) < last]
        require([row[0] for row in valid] == list(range(first, last)), f"{path}: mode coverage")
        for mode, n, f, s, suite in valid:
            require(f == s == "0" and n == "858", f"{path}: mode {mode} totals {(n, f, s)}")
            require("TEST: max_pool_s8, passed=42, failed=0, skipped=0" in suite,
                    f"{path}: mode {mode} max-pool tests")
            totals.append(mode)
    print(f"All {len(totals)} modes passed 858 checks each, including 42 max-pool checks per mode.")


def controls():
    for label in CONTROLS:
        path = BASE / "logs" / label / "run-1.log"
        text = read_boot(path)
        require("BENCH_DONE cases=104 failures=0 skipped=0" in text, f"{path}: control failed")
        cache = re.findall(r"^POOL_CACHE .+$", text, re.M)
        require(len(cache) == 1, f"{path}: cache configuration")
        rows = {(int(w), int(h), int(c), int(f), mem, mode): tuple(map(int, values))
                for mode, mem, cycles, ok, miss, dbus, insn, store, tie, dep, w, h, c, f in RECORD.findall(text)
                if ok == "1" for values in [(cycles, miss, dbus, insn, store, tie, dep)]}
        print(f"\n### {label}\n\n{cache[0]}\n")
        print("| Shape | Memory | Master cycles | V0 cycles | V0/master | Master PSRAM misses | V0 PSRAM misses |")
        print("|---|---|---:|---:|---:|---:|---:|")
        for *key, _, _ in REVIEW:
            a = rows[(*key, "master")]
            b = rows[(*key, "v0")]
            print(f"| {row_name(key)} | {a[0]:,} | {b[0]:,} | {b[0]/a[0]:.3f} | {a[1]:,} | {b[1]:,} |")


def order():
    expected = {"master_ab", "v0_ab", "fit0_ab", "master_ba", "fit0_ba", "v0_ba"}
    boots = []
    for i in range(1, 6):
        path = BASE / "logs" / "order64" / f"run-{i}.log"
        text = read_boot(path)
        require("BENCH_DONE cases=44 failures=0 skipped=0" in text, f"{path}: order probe failed")
        all_rows = RECORD.findall(text)
        rows = {rec[0]: int(rec[2]) for rec in all_rows
                if rec[1] == "ext" and rec[3] == "1" and rec[-4:] == ("64", "32", "16", "3")}
        require(len(all_rows) == 18 and all(r[3] == "1" for r in all_rows)
                and rows.keys() == expected, f"{path}: order/second-batch records")
        boots.append(rows)
    print("| Group | Master | First candidate | Second candidate |")
    print("|---|---:|---:|---:|")
    for suffix, first, second in (("ab", "v0", "fit0"), ("ba", "fit0", "v0")):
        values = [median(boot[f"{mode}_{suffix}"] for boot in boots)
                  for mode in ("master", first, second)]
        print(f"| {first} → {second} | {values[0]:,} | {values[1]:,} | {values[2]:,} |")


def interleaved():
    labels = ("master", "pr", "direct")
    firmware_hash = {
        "master": BASE / "reference" / "logs" / "master-bench_app.sha256",
        "pr": BASE / "reference" / "logs" / "pr-bench_app.sha256",
        "direct": BASE / "logs" / "pair64" / "firmware.sha256",
    }
    log_dir = BASE / "logs" / "interleaved-standalone"
    runs = {name: [standalone_boot(log_dir / f"{name}-{i}.log", firmware_hash[name])
                   for i in range(1, 6)] for name in labels}
    reference = runs["master"][0][1]
    require(all(placement == reference for samples in runs.values() for _, placement in samples),
            "Tensor addresses differ between interleaved standalone images")
    print("| Shape | Memory | Master | Current PR | Direct pair | Direct change vs master | Speedup vs master |")
    print("|---|---|---:|---:|---:|---:|---:|")
    for *key, _, _ in REVIEW:
        shape = tuple(key)
        master, pr, direct = (median(cycles[shape] for cycles, _ in runs[label]) for label in labels)
        print(f"| {row_name(shape)} | {master:,} | {pr:,} | {direct:,} | "
              f"{100*(direct/master-1):+.4f}% | {master/direct:.4f}× |")


def direct_sweep():
    rows, _ = summarize("direct-sweep", 5)
    shapes = {shape for shape, _ in rows}
    require(len(shapes) == 64 and len(rows) == 192, "Unexpected direct sweep coverage")
    ranking(rows)
    new_losses = sum(rows[shape, "direct"][0] > rows[shape, "master"][0] >= rows[shape, "v0"][0]
                     for shape in shapes)
    print()
    print(f"The direct-pair finalist turned {new_losses} V0 wins or ties against master into losses.")
    print()
    print("| Shape | Memory | Master | Current PR | Direct pair | Direct change vs master |")
    print("|---|---|---:|---:|---:|---:|")
    for shape in sorted(shapes):
        master, pr, direct = (rows[shape, label][0] for label in ("master", "v0", "direct"))
        if direct > master:
            print(f"| {row_name(shape)} | {master:,} | {pr:,} | {direct:,} | {100*(direct/master-1):+.3f}% |")


if __name__ == "__main__":
    import sys
    targets = {"standalone": standalone, "tests": tests, "controls": controls, "order": order,
               "pair": lambda: standalone("pair64", "Direct pair"), "interleaved": interleaved,
               "direct-sweep": direct_sweep}
    targets[sys.argv[1]]()
