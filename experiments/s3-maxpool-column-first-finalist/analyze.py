#!/usr/bin/env python3
"""Validate on-board runs and summarize matched cycle/counter measurements."""
import argparse
from collections import Counter
import csv
from pathlib import Path
import re
from statistics import median

BASE = Path(__file__).resolve().parent
METRICS = ("cycles", "spiram_miss", "dbus", "instructions", "store_full", "tie", "dependency")
V2 = ("t4", "t8", "t16", "t32")
V3 = ("b4", "b8", "b16", "b32")
REVIEW = (
    (16, 16, 16, 3, "int", 11954, 7239),
    (16, 16, 16, 3, "ext", 13087, 7239),
    (6, 6, 128, 5, "ext", 12837, 10748),
    (12, 12, 128, 5, "ext", 54267, 40069),
    (20, 20, 128, 5, "ext", 305809, 337848),
    (32, 32, 64, 3, "ext", 379449, 443358),
    (56, 56, 32, 3, "ext", 836649, 903836),
)
SHAPE = r"input (\d+)x(\d+)x(\d+), filter ([35])x[35], pad [12], stride 1"
RECORD = re.compile(r"^MET (\w+) (int|ext) (\d+) ([01]) " + r"(\d+) " * 6 + SHAPE + "$", re.M)
AUDIT = re.compile(r'^POOL_(INPUT|OUTPUT) mem=(int|ext) bytes=(\d+) .+ result=(\w+) shape="' + SHAPE + '"$', re.M)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_boot(path, firmware_hash=None):
    raw = re.sub(r"\x1b\[[0-9;]*m", "", path.read_text(errors="replace"))
    _, marker, text = raw.partition("CAPTURE_RESET_SENT")
    require(marker and "ESP-ROM:esp32s3" in text, f"{path}: missing reset")
    text = text[text.index("ESP-ROM:esp32s3"):]
    require("Guru Meditation" not in text and "watchdog got triggered" not in text,
            f"{path}: firmware exception")
    expected = (firmware_hash or path.parent / "firmware.sha256").read_text().split()[0]
    identity = re.findall(r"ELF file SHA256:\s+(\w+)", text)
    require(len(identity) == 1 and expected.startswith(identity[0]), f"{path}: ELF fingerprint")
    return text


def bench(path):
    text = read_boot(path)
    totals = re.findall(r"^BENCH_DONE cases=(\d+) failures=(\d+) skipped=(\d+)$", text, re.M)
    require(len(totals) == 1 and totals[0][1:] == ("0", "0"), f"{path}: totals {totals}")
    cache = re.findall(r"^POOL_CACHE .+$", text, re.M)
    require(len(cache) == 1 and "psram_mhz_config=80" in cache[0], f"{path}: invalid cache or PSRAM")
    require("240000000 Hz" in text and "Found 8MB PSRAM device" in text, f"{path}: unexpected board")
    rows = {}
    for found in RECORD.findall(text):
        name, mem, cycles, checked, misses, dbus, insn, store, tie, dep, w, h, c, filt = found
        key = (int(w), int(h), int(c), int(filt), mem), name
        require(checked == "1" and key not in rows, f"{path}: invalid timing/correctness row {key}")
        rows[key] = tuple(map(int, (cycles, misses, dbus, insn, store, tie, dep)))
    audits = Counter()
    for direction, mem, size, result, w, h, c, filt in AUDIT.findall(text):
        shape = int(w), int(h), int(c), int(filt), mem
        require(result == "ok" and int(size) == int(w) * int(h) * int(c), f"{path}: allocation {shape}")
        audits[shape, direction] += 1
    shapes = {shape for shape, _ in rows}
    require(shapes and all(audits[shape, d] == 1 for shape in shapes for d in ("INPUT", "OUTPUT"))
            and len(audits) == 2 * len(shapes), f"{path}: incorrect or incomplete allocation audit")
    modes = sorted({mode for _, mode in rows})
    require({"master", "v0"} <= set(modes) and len(rows) == len(shapes) * len(modes),
            f"{path}: missing timings (recorded {len(rows)}/{len(shapes) * len(modes)})")
    return rows, cache[0]


def summarize(label, runs, logs_dir=BASE / "logs"):
    directory = logs_dir / label
    samples = [bench(directory / f"run-{i}.log") for i in range(1, runs + 1)]
    initial, cache = samples[0]
    require(all(rows.keys() == initial.keys() and c == cache for rows, c in samples),
            f"{label}: unequal shape, mode, or cache coverage")
    medians = {key: tuple(int(median(m)) for m in zip(*(r[key] for r, _ in samples))) for key in initial}
    output = directory / "metrics.csv"
    with output.open("w", newline="") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(("width", "height", "channels", "filter", "memory", "mode", *METRICS, "cycle_samples"))
        for shape, mode in sorted(medians):
            writer.writerow((*shape, mode, *medians[shape, mode],
                             "/".join(str(r[shape, mode][0]) for r, _ in samples)))
    return medians, cache


def row_name(shape):
    w, h, c, f, mem = shape
    return f"{f}×{f}, {w}×{h}×{c} | {'PSRAM' if mem == 'ext' else 'Internal RAM'}"


def ranking(rows):
    shapes = {shape for shape, _ in rows}
    modes = sorted({mode for _, mode in rows})
    print(f"Measured {len(shapes)} matched shapes and placements per mode.")
    print()
    print("| Implementation | Wins vs master | Ties | Losses | >1% slower than master | >1% slower than V0 | Worst ratio vs master |")
    print("|---|---:|---:|---:|---:|---:|---:|")
    for mode in modes:
        ratios = [rows[shape, mode][0] / rows[shape, "master"][0] for shape in shapes]
        vs_v0 = sum(rows[shape, mode][0] > 1.01 * rows[shape, "v0"][0] for shape in shapes)
        print(f"| {mode} | {sum(r < 1 for r in ratios)} | {sum(r == 1 for r in ratios)} | "
              f"{sum(r > 1 for r in ratios)} | {sum(r > 1.01 for r in ratios)} | {vs_v0} | {max(ratios):.3f} |")


def report(rows, cache):
    modes = sorted({mode for _, mode in rows})
    print(f"Cache configuration from the board was {cache}.\n")
    print("| Shape | Memory | Master | Current PR | V1 | V2 best tile | V3 best band | V4 best | Best | Speedup vs master |")
    print("|---|---|---:|---:|---:|---:|---:|---:|---|---:|")
    for *parts, _, _ in REVIEW:
        shape = tuple(parts)
        values = {mode: rows[shape, mode][0] for mode in modes}
        v2 = min((m for m in V2 if m in values), key=values.get)
        v3 = min((m for m in V3 if m in values), key=values.get)
        v4 = min((m for m in values if m not in {"master", "v0", "v1", *V2, *V3}), key=values.get)
        best = min(values, key=values.get)
        print(f"| {row_name(shape)} | {values['master']:,} | {values['v0']:,} | {values['v1']:,} | "
              f"{values[v2]:,} ({v2}) | {values[v3]:,} ({v3}) | {values[v4]:,} ({v4}) | {best} ({values[best]:,}) | "
              f"{values['master'] / values[best]:.3f}× |")
    print()
    ranking(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("label")
    parser.add_argument("--runs", type=int, default=5)
    parser.add_argument("--logs-dir", type=Path, default=BASE / "logs")
    args = parser.parse_args()
    rows, cache = summarize(args.label, args.runs, args.logs_dir)
    if any(mode in V2 for _, mode in rows):
        report(rows, cache)
    else:
        print(cache)
        ranking(rows)


if __name__ == "__main__":
    main()
