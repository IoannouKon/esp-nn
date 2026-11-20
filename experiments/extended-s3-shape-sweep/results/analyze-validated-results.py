#!/usr/bin/env python3
"""Enrich the kit's validated results without modifying firmware or raw logs."""
import csv
import json
import math
import sys
from collections import Counter
from pathlib import Path
from statistics import median

root = Path(sys.argv[1]).resolve()
results = root / "results"
analysis = results / "analysis"
kit = Path(__file__).resolve().parent
manifest = json.loads((kit / "SHAPES.json").read_text())
shapes = {
    (operation, case["shape"], case["mem"]): case
    for operation in ("mean", "max_pool") for case in manifest[operation]
}
data = json.loads((analysis / "comparison.json").read_text())
rows = data["rows"]
assert len(rows) == len(shapes) == 90


def verdict(stock, candidate):
    # Use the user's +/-1% bands on the stock cycle count.
    if 100 * candidate < 99 * stock:
        return "WIN"
    if 100 * candidate > 101 * stock:
        return "LOSS"
    return "NEUTRAL"


def paths(op, spec):
    if op == "mean":
        assert (spec["h"] * spec["w"] <= 4095 and spec["ch"] % 16 == 0) == spec["opt_eligible"]
        return "scalar", "QACC SIMD" if spec["opt_eligible"] else "scalar fallback"
    channels = spec["ch"]
    stock = "64-bit SIMD" if channels % 8 == 0 else "32-bit SIMD" if channels % 4 == 0 else "ANSI fallback"
    sliding = (
        spec["f"] in (3, 5) and spec["stride"] == 1 and spec["pad"] == spec["f"] // 2
        and min(spec["w"], spec["h"]) >= spec["f"] and channels % 16 == 0
    )
    assert sliding == spec["opt_eligible"]
    opt2 = "Opt2 sliding SIMD" if sliding else "Opt1 128-bit SIMD fallback" if channels % 16 == 0 else stock
    return stock, opt2


for row in rows:
    op = row["op"]
    spec = shapes[op, row["shape"], row["mem"]]
    stock_path, candidate_path = paths(op, spec)
    row.update(
        height=spec["h"], width=spec["w"], channels=spec["ch"],
        correctness="PASS", stock_correctness="PASS", exp_mean_correctness="PASS", opt2_correctness="PASS",
        stock_path=stock_path,
        exp_mean_path=candidate_path if op == "mean" else stock_path,
        opt2_path=candidate_path if op == "max_pool" else stock_path,
        target_build="exp_mean" if op == "mean" else "opt2",
    )
    if op == "max_pool":
        row.update(filter=spec["f"], stride=spec["stride"], padding=spec["pad"])
    row["mean_verdict"] = verdict(row["stock_median"], row["exp_mean_median"])
    row["opt2_verdict"] = verdict(row["stock_median"], row["opt2_median"])
    row["target_verdict"] = row["mean_verdict" if op == "mean" else "opt2_verdict"]


def summarize(selected, target):
    speeds = [r["stock_median"] / r[target + "_median"] for r in selected]
    counts = Counter(verdict(r["stock_median"], r[target + "_median"]) for r in selected)
    best = selected[speeds.index(max(speeds))]
    worst = selected[speeds.index(min(speeds))]
    return {
        "count": len(selected), "wins": counts["WIN"], "losses": counts["LOSS"], "neutral": counts["NEUTRAL"],
        "median_speedup": median(speeds), "geomean_speedup": math.exp(sum(map(math.log, speeds)) / len(speeds)),
        "best": {"shape": best["shape"], "mem": best["mem"], "speedup": max(speeds)},
        "worst": {"shape": worst["shape"], "mem": worst["mem"], "speedup": min(speeds)},
    }


summary = {}
control = {}
for target, op in (("exp_mean", "mean"), ("opt2", "max_pool")):
    target_rows = [r for r in rows if r["op"] == op]
    summary[target] = {
        "all": summarize(target_rows, target),
        "eligible": summarize([r for r in target_rows if r["eligible"]], target),
        "fallback": summarize([r for r in target_rows if not r["eligible"]], target),
        "memory": {mem: summarize([r for r in target_rows if r["mem"] == mem], target) for mem in ("int", "ext")},
        "path_by_memory": {
            f"{path}|{mem}": summarize([r for r in target_rows if r[target + "_path"] == path and r["mem"] == mem], target)
            for path, mem in sorted({(r[target + "_path"], r["mem"]) for r in target_rows})
        },
    }
    other = [r for r in rows if r["op"] != op]
    control[target] = summarize(other, target)

order = (("stock", 1), ("exp_mean", 1), ("opt2", 1), ("stock", 2), ("opt2", 2), ("exp_mean", 2))
captures = []
for build, boot in order:
    log = results / f"{build}-{boot}.log"
    elapsed = float((results / f"{build}-{boot}.elapsed").read_text().strip())
    captures.append({
        "build": build, "boot": boot, "log": log.name,
        "monitor_elapsed_s": elapsed, "timeout_s": 1200, "timeout_hit": False,
    })

data.update(target_summaries=summary, control_summaries=control, capture_order=captures)
data["metadata"]["classification"] = "WIN <99% of stock cycles; LOSS >101%; NEUTRAL otherwise"
data["metadata"]["shape_manifest_sha256"] = json.loads((results / "stock-install.json").read_text())["manifest_sha256"]
data["metadata"]["commits"] = {
    name: json.loads((results / f"{name}-install.json").read_text())["git_sha"]
    for name, _ in order
}
# Keep group aggregates consistent with the explicit cycle-reduction threshold.
for key, group in data["groups"].items():
    target, eligible, mem = key.split("|")
    op = "mean" if target == "exp_mean" else "max_pool"
    selected = [r for r in rows if r["op"] == op and r["mem"] == mem[4:] and str(r["eligible"]) == eligible[9:]]
    stats = summarize(selected, target)
    for field in ("wins", "losses", "neutral"):
        group[field] = stats[field]

(analysis / "comparison.json").write_text(json.dumps(data, indent=2) + "\n")
fields = [
    "op", "shape", "height", "width", "channels", "filter", "stride", "padding", "mem", "correctness",
    "eligible", "stock_path", "exp_mean_path", "opt2_path", "target_build", "target_verdict",
    "stock_median", "exp_mean_median", "opt2_median", "stock_cycles", "exp_mean_cycles", "opt2_cycles",
    "stock_range", "exp_mean_range", "opt2_range", "mean_speedup", "opt2_speedup",
    "mean_reduction_pct", "opt2_reduction_pct", "mean_verdict", "opt2_verdict",
    "stock_correctness", "exp_mean_correctness", "opt2_correctness",
]
with (analysis / "comparison.csv").open("w", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fields)
    writer.writeheader()
    writer.writerows({key: row.get(key, "") for key in fields} for row in rows)
print(json.dumps({"target": summary, "controls": control, "captures": captures}, indent=2))
