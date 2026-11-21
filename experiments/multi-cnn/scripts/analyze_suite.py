#!/usr/bin/env python3
"""Gate complete-CNN comparisons on qualified physical captures and exact outputs."""
from collections import Counter
import csv
from hashlib import sha256
import json
from pathlib import Path
import re
from statistics import median

results = Path(__file__).resolve().parents[1] / "results"
manifest = json.loads((results / "manifest.json").read_text())
groups = {
    "core": "mnist_fixed max3 max5 mean_only both depthwise_both avg_control neutral_control person_detection".split(),
    "mobiles": "mobilenet_v2 mobilenet_v3_small".split(),
    "lite0": ["efficientnet_lite0"],
}
versions = ("stock", "opt2", "mean", "combined")
pairs = (("stock", "opt2"), ("stock", "mean"), ("stock", "combined"),
         ("opt2", "combined"), ("mean", "combined"))
sections = re.compile(r"^CNN_MODEL_BEGIN name=(\w+)\s*\n(.*?)^CNN_MODEL_DONE name=\1 ok=(\d+)\s*\n", re.M | re.S)
ansi = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")

def read_boot(path):
    if not path.exists():
        return {}
    text = ansi.sub("", path.read_text(errors="replace"))
    complete = ("CNN_SUITE_DONE\n" in text and "Guru Meditation" not in text and
                "Task watchdog got triggered" not in text and "Stack canary watchpoint triggered" not in text)
    return {name: (whole.group(), body, ok == "1" and complete)
            for whole in sections.finditer(text) for name, body, ok in [whole.groups()]}

def parse(body, done, model):
    times = [(int(i), int(v)) for i, v in re.findall(r"^CNN_RUN index=(\d+) us=(\d+)$", body, re.M)]
    output = re.search(r"^CNN_OUTPUT bytes=(\d+) hash_fnv1a=(\w+) stable=(\d) hex=([0-9a-f]+)$", body, re.M)
    start = re.search(r"^CNN_START cpu_mhz=(\d+) model_bytes=(\d+) input_bytes=(\d+).*arena_cap=(\d+) arena_used=(\d+)", body, re.M)
    valid = False
    buf = None
    alt = {int(i): h for i, h in re.findall(r"^CNN_VALIDATION index=(\d+) hex=([0-9a-f]+)$", body, re.M)}
    if output and start:
        length, fnv, stable, values = output.groups()
        buf = bytes.fromhex(values)
        h = 2166136261
        for byte in buf:
            h = (h ^ byte) * 16777619 & 0xffffffff
        m = manifest[model]
        valid = (done and stable == "1" and len(buf) == int(length) and f"{h:08x}" == fnv and
                 [i for i, _ in times] == list(range(len(times))) and len(times) >= 30 and
                 tuple(map(int, start.groups()[:3])) == (240, m["model_bytes"], m["input_bytes"]))
    nums = [v for _, v in times]
    return dict(valid=valid, times_us=nums, median_us=median(nums) if nums else None,
                min_us=min(nums) if nums else None, max_us=max(nums) if nums else None,
                arena_capacity=int(start[4]) if start else None, arena_used=int(start[5]) if start else None,
                output_hex=buf.hex() if buf else None, output_sha256=sha256(buf).hexdigest() if buf else None,
                validation_outputs_hex=alt, errors=re.findall(r"^CNN_MODEL_ERROR reason=(.*)$", body, re.M))

def dispatch(body="", done=False):
    pool = [int(v) for v in re.findall(r"sliding_rows=(\d+)", body)]
    checks = [(int(a), int(b)) for a, b in re.findall(r"compared=(\d+) mismatches=(\d+)", body)]
    qacc = re.search(r"CNN_QACC diagnostic_blocks=(\d+)", body)
    return dict(done=done, rows_per_pool=pool, sliding_rows=sum(pool),
                mean_esnn_layers=len(checks), mean_reference_layers=body.count("route=tflm_reference"),
                mean_elements_compared=sum(a for a, _ in checks), mean_mismatches=sum(b for _, b in checks),
                qacc_blocks=int(qacc[1]) if qacc else 0)

def output_difference(expected, actual, dtype):
    left, right = bytes.fromhex(expected), bytes.fromhex(actual)
    assert len(left) == len(right)
    def q(b):
        return b - 256 if dtype == "INT8" and b >= 128 else b
    diffs = [abs(q(a) - q(b)) for a, b in zip(left, right)]
    return {"mismatched_elements": sum(v != 0 for v in diffs),
            "max_abs_difference": max(diffs, default=0)}

def compare(name, a, b, model, ready):
    fw = model["firmwares"]
    ta, tb = (fw[v]["median_us"] for v in (a, b))
    row = dict(model=name, baseline=a, candidate=b, baseline_us=ta, candidate_us=tb,
               speedup=None, reduction_pct=None, cycle_delta_est=None, outputs_exact=model["exact_outputs"],
               threshold=None, verdict="INCONCLUSIVE", note=None, boot_reductions_pct=None)
    runs = [r for v in versions for r in fw[v]["runs"]]
    d = model["dispatch"]
    if not ready:
        if model.get("unsupported_reason"):
            row.update(verdict="SKIP", note=model["unsupported_reason"])
        elif runs and all(r["errors"] for r in runs):
            row.update(verdict="SKIP", note="; ".join(sorted({e for r in runs for e in r["errors"]})))
        else:
            row["note"] = "requires two qualified boots per firmware"
    elif not model["exact_outputs"] or not model["validation_matches"]:
        row["note"] = "complete output bytes differ"
    elif not d["done"]:
        row["note"] = "requires dispatch diagnostics"
    elif (manifest[name]["operator_counts"].get("MEAN") and
         any(v in ("mean", "combined") for v in (a, b)) and
         (not d["qacc_blocks"] or not d["mean_esnn_layers"] or d["mean_mismatches"])):
        row["note"] = "requires actual QACC execution and exact MEAN validation"
    else:
        reduction = 100 * (ta - tb) / ta
        boot_reductions = [100 * (ra["median_us"] - rb["median_us"]) / ra["median_us"]
                           for ra, rb in zip(fw[a]["runs"], fw[b]["runs"])]
        threshold = "WIN" if reduction > 1 else "LOSS" if reduction < -1 else "NEUTRAL"
        adds_pool = a in ("stock", "mean") and b in ("opt2", "combined")
        adds_mean = a in ("stock", "opt2") and b in ("mean", "combined")
        exercised = (adds_pool and d["sliding_rows"]) or (adds_mean and d["qacc_blocks"])
        note = ""
        verdict = threshold
        if threshold != "NEUTRAL" and not exercised:
            verdict, note = "INCONCLUSIVE", "threshold crossed without a targeted path"
        elif threshold != "NEUTRAL" and any(r * reduction <= 0 for r in boot_reductions):
            verdict, note = "INCONCLUSIVE", "paired boot medians reverse direction"
        elif threshold != "NEUTRAL" and min(map(abs, boot_reductions)) <= 1:
            note = "one paired boot within 1%"
        row.update(speedup=ta/tb, reduction_pct=reduction, cycle_delta_est=(ta-tb)*240,
                   threshold=threshold, verdict=verdict, note=note, boot_reductions_pct=boot_reductions)
    return row

data, rows = {}, []
for group, names in groups.items():
    folder = results / "logs" / f"suite_{group}"
    diagnostics = read_boot(folder / "combined-diagnostic.log")
    boots = {v: [read_boot(folder / f"{v}-{i}.log") for i in (1, 2)] for v in versions}
    for name in names:
        fw = {}
        for v, captures in boots.items():
            runs = []
            for boot, content in enumerate(captures, 1):
                if name not in content:
                    continue
                section, body, done = content[name]
                model_log = results / "logs" / name / f"{v}-{boot}.log"
                model_log.parent.mkdir(parents=True, exist_ok=True)
                model_log.write_text(section)
                run = parse(body, done, name)
                run.update(boot_index=boot, log=str(model_log.relative_to(results)),
                           raw_log=str((folder / f"{v}-{boot}.log").relative_to(results)))
                runs.append(run)
            fw[v] = dict(runs=runs, median_us=median(r["median_us"] for r in runs)
                         if len(runs) == 2 and all(r["valid"] for r in runs) else None)
        runs = [r for v in versions for r in fw[v]["runs"]]
        ready = len(runs) == 8 and all(r["valid"] for r in runs)
        exact = len({r["output_hex"] for r in runs}) == 1 if ready else None
        alt = len({tuple(sorted(r["validation_outputs_hex"].items())) for r in runs}) == 1 if ready else None
        count = len(runs[0]["validation_outputs_hex"]) if alt else 0
        host = manifest[name]["host_reference"].get("outputs_hex")
        host_matches = None
        host_fixed_diff = None
        host_default_diff = None
        if exact and host:
            values = [runs[0]["output_hex"]] + list(runs[0]["validation_outputs_hex"].values())
            host_matches = sum(a == b for a, b in zip(host, values))
            dtype = manifest[name]["output"]["dtype"]
            host_fixed_diff = output_difference(host[0], values[0], dtype)
            default = manifest[name]["host_tflite"].get("outputs_hex")
            if default:
                host_default_diff = output_difference(default[0], values[0], dtype)
        _, detail, done = diagnostics.get(name, ("", "", False))
        errors = re.findall(r"^CNN_MODEL_ERROR reason=(.*)$", detail, re.M)
        unsupported = None
        if not runs and errors and (folder / "documented-skips.json").exists():
            unsupported = json.loads((folder / "documented-skips.json").read_text()).get(name)
        data[name] = dict(firmwares=fw, dispatch=dispatch(detail, done), exact_outputs=exact,
                          unsupported_reason=unsupported,
                          validation_matches=alt, validation_count=count, host_reference_matches=host_matches,
                          host_reference_fixed_diff=host_fixed_diff,
                          host_default_fixed_diff=host_default_diff)
        rows.extend(compare(name, a, b, data[name], ready) for a, b in pairs)

(results / "comparison.json").write_text(json.dumps({"models": data, "comparisons": rows}, indent=2) + "\n")
with (results / "comparison.csv").open("w", newline="") as output:
    writer = csv.DictWriter(output, rows[0].keys())
    writer.writeheader()
    writer.writerows(rows)
for a, b in pairs:
    subset = [r for r in rows if (r["baseline"], r["candidate"]) == (a, b)]
    print(a, b, dict(Counter(r["verdict"] for r in subset)))
    for r in subset:
        print(r["model"], r["baseline_us"], r["candidate_us"], r["verdict"], r["note"])
