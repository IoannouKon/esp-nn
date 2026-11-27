#!/usr/bin/env python3
"""Report matched medians and a non-measured pointwise fallback reference."""
import argparse
from math import exp, log
from pathlib import Path
import re
from statistics import median
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "s3-maxpool-column-first-finalist"))
from analyze import REVIEW, bench, read_boot, require, row_name

INITIAL = ("master", "v0", "e1", "e2", "e3", "e4", "prefix", "batch16",
           "stream", "pair_generic", "direct")
SWEEP = ("master", "v0", "v0_policy", "e4_policy", "e4", "stream", "five_policy", "direct")


def geomean(ratios):
    return exp(sum(map(log, ratios)) / len(ratios))


def load(directory, modes, expected_shapes):
    runs = []
    orders = []
    for i in range(1, 6):
        path = directory / f"run-{i}.log"
        rows, cache = bench(path)
        require("dcache_kib=64" in cache and "dcache_ways_config=8" in cache
                and "dcache_line=64" in cache, f"{path}: default cache")
        order = re.findall(r"^ABLATION_ORDER first=(\w+)", read_boot(path), re.M)
        require(len(order) == 1 and order[0] in modes, f"{path}: missing order marker")
        orders.append(order[0])
        shape_set = {shape for shape, _ in rows}
        require(len(shape_set) == expected_shapes and
                rows.keys() == {(shape, m) for shape in shape_set for m in modes},
                f"{path}: case/mode coverage")
        if runs:
            require(rows.keys() == runs[0].keys(), f"{path}: mismatched shapes")
        runs.append(rows)
    values = {key: int(median(row[key][0] for row in runs)) for key in runs[0]}
    return values, runs, orders


def oracle_summary(values, modes):
    shapes = sorted({shape for shape, _ in values})
    print("| Mode | Geomean speedup vs master | Geomean speedup vs V0 | Wins vs master | Losses >1% | Worst vs master | Geomean cycles / oracle |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for mode in (*modes, "oracle"):
        master = [values[s, "master"] for s in shapes]
        v0 = [values[s, "v0"] for s in shapes]
        ideal = [min(a, b) for a, b in zip(master, v0)]
        data = ideal if mode == "oracle" else [values[s, mode] for s in shapes]
        against_master = [a/b for a, b in zip(data, master)]
        print(f"| {mode} | {1/geomean(against_master):.3f}× | {geomean([b/a for a,b in zip(data,v0)]):.3f}× | "
              f"{sum(a < b for a,b in zip(data,master))}/{len(shapes)} | "
              f"{sum(a > 1.01 for a in against_master)} | {max(against_master):.3f}× | "
              f"{geomean([a/b for a,b in zip(data,ideal)]):.3f}× |")


def isolations(values):
    comparisons = (
        ("v0", "e1", "all"), ("v0", "e3", "all"), ("e3", "e2", "all"),
        ("v0", "e4", "all"), ("prefix", "stream", "multi"),
        ("batch16", "stream", "multi"), ("stream", "pair_generic", "paired"),
        ("pair_generic", "direct", "paired"),
    )
    print("\n| Control → candidate | Cases | Geomean cycle reduction | Min | Max |")
    print("|---|---:|---:|---:|---:|")
    for control, candidate, eligible in comparisons:
        samples = [values[shape, candidate] / cycles for (shape, mode), cycles in values.items()
                   if mode == control and (eligible == "all"
                   or (eligible == "multi" and shape[2] > 16)
                   or (eligible == "paired" and shape[2:4] == (32, 3)))]
        print(f"| {control} → {candidate} | {len(samples)} | {100*(1-geomean(samples)):.2f}% | "
              f"{100*(1-max(samples)):.2f}% | {100*(1-min(samples)):.2f}% |")


def reviewer_table(values, modes, include_extras):
    shapes = [tuple(row[:-2]) for row in REVIEW]
    if include_extras:
        shapes.extend(sorted({shape for shape, _ in values} - set(shapes)))
    print("| Shape | Memory | " + " | ".join(modes) + " |")
    print("|---|---|" + "---:|" * len(modes))
    for shape in shapes:
        print(f"| {row_name(shape)} | " + " | ".join(f"{values[shape, m]:,}" for m in modes) + " |")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("log_directory", type=Path)
    parser.add_argument("stage", choices=("initial", "sweep"))
    arguments = parser.parse_args()
    modes, shapes = (INITIAL, 9) if arguments.stage == "initial" else (SWEEP, 64)
    values, runs, orders = load(arguments.log_directory, modes, shapes)
    print("First variant per boot was " + ", ".join(orders) + ".\n")
    reviewer_table(values, modes, include_extras=arguments.stage == "initial")
    print()
    oracle_summary(values, modes)
    if arguments.stage == "initial":
        isolations(values)
    else:
        print("\n| Shape | Memory | Mode | Master | Median | Median / master |")
        print("|---|---|---|---:|---:|---:|")
        for shape in sorted({shape for shape, _ in values}):
            master = values[shape, "master"]
            for mode in modes[2:]:
                cycles = values[shape, mode]
                if cycles > 1.01 * master:
                    print(f"| {row_name(shape)} | {mode} | {master:,} | {cycles:,} | {cycles/master:.3f}× |")
    with (arguments.log_directory / "medians.tsv").open("w") as file:
        print("width\theight\tchannels\tfilter\tmemory\tmode\tmedian\tboot_cycles", file=file)
        for (shape, mode), value in sorted(values.items()):
            fields = (*shape, mode, value, "/".join(str(row[shape, mode][0]) for row in runs))
            print(*fields, sep="\t", file=file)


if __name__ == "__main__":
    main()
