#!/usr/bin/env python3
"""Validate board evidence and retain original results alongside the follow-up."""
import argparse
import csv
import hashlib
import json
import re
import shlex
import statistics
import sys
from pathlib import Path

EXT = Path(__file__).resolve().parents[1]
KIT = EXT.parent
VARIANTS = ("stock", "opt2", "mean", "combined")
NEW_MODELS = ("cifar_mean_wide", "cifar_mean_large")
QACC_MODELS = ("mean_only", "both", "depthwise_both", *NEW_MODELS)
sys.path.insert(0, str(KIT / "scripts"))
from compare_cnn import parse as parse_original_capture

PROFILE = r"^CNN_PROFILE index=(\d+) us=(\d+) cycles=(\d+) mean_us=(\d+) mean_cycles=(\d+) calls=(\d+)"
EMPTY = r"^CNN_EMPTY index=(\d+) us=(\d+) cycles=(\d+)"
CASE_OUTPUT = r"^CNN_CASE_OUTPUT index=(\d+) bytes=(\d+) hex=([0-9a-f]+)"
MEAN_CHECK = (r"^CNN_MEAN route=esp_nn shape=(\d+)x(\d+)x(\d+) input=(0x[0-9a-f]+) "
              r"output=(0x[0-9a-f]+) zp_in=(-?\d+) zp_out=(-?\d+) multiplier=(\d+) shift=(-?\d+) "
              r"trials=(\d+) compared=(\d+) mismatches=(\d+)")
ORIGINAL = json.loads((KIT / "results/analysis/compare.json").read_text())["models"]
SDK_HASH = ORIGINAL["mean_only"]["raw"]["stock"][0]["sdkconfig_sha256"]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def relative(path):
    return path.relative_to(KIT).as_posix()


def model_dir(model):
    return (EXT if model in NEW_MODELS else KIT) / "models" / model


def read_capture(path):
    text = path.read_text(errors="replace").rsplit("CAPTURE_RESET_SENT", 1)[-1]
    require("CNN_ERROR" not in text and "Guru Meditation" not in text and "Task watchdog got triggered" not in text,
            f"Firmware failure in {path}")
    require("cpu freq: 240000000 Hz" in text and "Single core mode" in text and "Found 8MB PSRAM device" in text,
            f"Unexpected clock, core count or PSRAM in {path}")
    require(digest(path.with_suffix(".sdkconfig").read_bytes()) == SDK_HASH, f"SDK settings differ in {path}")
    hashes = re.findall(r"ELF file SHA256:\s+([a-f0-9]+)", text)
    identifier = path.with_suffix(".elf.sha256").read_text().split()[0]
    require(len(hashes) == 1 and identifier.startswith(hashes[0]), f"Wrong flashed ELF in {path}")
    return text


def verify_staged_sources(directory, variants, filename):
    records = []
    for variant in variants:
        sources = {}
        for row in (directory / filename.format(variant=variant)).read_text().splitlines():
            checksum, source = row.split(maxsplit=1)
            sources[Path(source).name] = checksum
        records.append(sources)
    require(all(row == records[0] for row in records), f"Different staged code or embedded data in {directory}")
    return records[0]


def validate_correctness(model, graph):
    directory = EXT / "results/diagnostics" / model
    fixtures = EXT / "models" / model
    meta = json.loads((fixtures / "correctness_inputs.json").read_text())
    raw = (fixtures / "correctness_inputs.bin").read_bytes()
    size = meta["input_size"]
    require(len(raw) == len(meta["cases"]) * size >= 10 * size, f"Incomplete inputs for {model}")
    for index, case in enumerate(meta["cases"]):
        require(digest(raw[index * size:(index + 1) * size]) == case["sha256"], f"Fixture hash differs in {model}")
    require(len({case["sha256"] for case in meta["cases"]}) == len(meta["cases"]), f"Duplicate fixtures for {model}")
    require(digest((model_dir(model) / "input.bin").read_bytes()) not in {case["sha256"] for case in meta["cases"]},
            f"Frozen input leaked into extra fixtures for {model}")
    source_hashes = verify_staged_sources(directory, VARIANTS, "{variant}-staged-source.sha256")

    h, w, channels = graph["input_shape"][1:]
    variants = {}
    for variant in VARIANTS:
        path = directory / f"{variant}-probe.log"
        text = read_capture(path)
        require("LOCAL_COMPONENT_SOURCE_CHECK_PASS" in (directory / f"{variant}-probe-source-check.txt").read_text(),
                f"Missing local component proof in {path}")
        require((directory / f"{variant}-probe-inputs.sha256").read_text().split()[0] == digest(raw),
                f"Incorrect embedded input fixtures in {path}")
        # The explicit reset can arrive while the flash tool's automatic boot
        # still emits output. Start after the verified boot's own CNN banner.
        text = text[text.index("CNN_START ", text.index("ELF file SHA256:")):]
        match = re.search(r"^CNN_CASE_DONE cases=(\d+) heap_integrity=ok arena_guard=ok stack_high_water_bytes=(\d+)",
                          text, re.M)
        require(match and int(match[1]) == len(meta["cases"]) and "CNN_PROBE_DONE" in text, f"Incomplete checks in {path}")
        parts = re.split(r"^CNN_CASE index=(\d+)\s*$", text, flags=re.M)
        require([int(n) for n in parts[1::2]] == list(range(len(meta["cases"]))), f"Wrong case indices in {path}")
        checks = []
        for index, (segment, case) in enumerate(zip(parts[2::2], meta["cases"])):
            match = re.search(MEAN_CHECK, segment, re.M)
            require(match, f"MEAN fallback or missing reference check in {path}, case {index}")
            dh, dw, dc, inp, out, zp_in, zp_out, mul, shift, trials, compared, mismatches = (
                int(value, 0) for value in match.groups())
            require((dh, dw, dc) == (h, w, channels) and (inp | out) & 15 == 0 and
                    (inp - out >= channels or out - inp >= h * w * channels) and
                    (zp_in, zp_out) == (graph["input_zero_point"], graph["output_zero_point"]) and
                    mul > 0 and -30 <= shift <= 0 and trials == 6 and compared == 2 * trials * channels and mismatches == 0,
                    f"MEAN compatibility or reference mismatch in {path}, case {index}")
            blocks = re.findall(r"^CNN_QACC diagnostic_blocks=(\d+)", segment, re.M)
            require(blocks == [str((trials + 1) * channels // 16 if variant in ("mean", "combined") else 0)],
                    f"Wrong QACC block count in {path}, case {index}")
            output = re.search(CASE_OUTPUT, segment, re.M)
            require(output and int(output[1]) == index and int(output[2]) * 2 == len(output[3]),
                    f"Incomplete output bytes in {path}, case {index}")
            checks.append({"index": index, "input_sha256": case["sha256"], "label": case["label"], "output_hex": output[3],
                           "desktop_reference_output_hex": case["desktop_reference_output_hex"],
                           "desktop_reference_match": output[3] == case["desktop_reference_output_hex"],
                           "mean_reference_bytes_compared": compared, "mean_reference_mismatches": mismatches,
                           "mean_effective_shift": shift, "mean_multiplier": mul, "qacc_blocks": int(blocks[0]),
                           "heap_integrity": True, "arena_guard": True})
        variants[variant] = {"log": relative(path), "checks": checks}
    outputs = [[case["output_hex"] for case in data["checks"]] for data in variants.values()]
    require(all(o == outputs[0] for o in outputs), f"Board output mismatch for {model}")
    return {"inputs": len(meta["cases"]), "variants": variants, "staged_hashes": source_hashes, "output_equality": True}


def timed_capture(path):
    content = read_capture(path)
    data = parse_original_capture(path)
    data["log"] = relative(path)
    symbols = path.with_suffix(".symbols.txt").read_text()
    require("__wrap_esp_nn_" not in symbols, f"Diagnostic linker instrumentation in {path}")
    require("LOCAL_COMPONENT_SOURCE_CHECK_PASS" in
            path.with_name(path.stem + "-source-check.txt").read_text(), f"Unverified linked sources in {path}")
    require("mean=guarded_esp_nn_bridge" in content, f"Missing adapter in {path}")
    qacc_expected = path.stem.split("-")[0] in ("mean", "combined")
    require(("esp_nn_mean_s8_16ch_qacc" in symbols) == qacc_expected, f"Unexpected MEAN symbol in {path}")
    return content, data


def compare_compile_flags(directory):
    commands = {}
    for variant in VARIANTS:
        entries = json.loads((directory / f"{variant}-compile-selected.json").read_text())
        pattern = re.compile(rf"/{variant}/(?=(?:app|esp-nn|esp-tflite-micro)(?:/|[=\s]|$))")
        commands[variant] = {pattern.split(entry["file"], maxsplit=1)[1]:
                              shlex.split(pattern.sub("/FIRMWARE/", entry["command"])) for entry in entries}
    stock = commands["stock"]
    require(len(stock) > 0, f"Missing compiled source evidence in {directory}")
    for variant, entries in commands.items():
        require(all(entries.get(unit) == command for unit, command in stock.items()),
                f"Compiler commands differ for common units in {directory}, {variant}")
    return len(stock)


def boot_median(boots, key):
    return statistics.median(statistics.median(boot[key]) for boot in boots)


def validate_profile(model, reference):
    directory = EXT / "results/profile" / model
    sources = verify_staged_sources(directory, VARIANTS, "{variant}-staged-source.sha256")
    by_variant = {}
    for variant in VARIANTS:
        boots = []
        for boot in (1, 2):
            path = directory / f"{variant}-{boot}.log"
            content, data = timed_capture(path)
            profile = [tuple(map(int, row)) for row in re.findall(PROFILE, content, re.M)]
            calibration = [tuple(map(int, row)) for row in re.findall(EMPTY, content, re.M)]
            require([p[0] for p in profile] == [c[0] for c in calibration] == list(range(30)),
                    f"Incomplete paired timing in {path}")
            require(all(p[5] == 1 and 0 < p[4] < p[2] and 0 <= p[3] < p[1] for p in profile),
                    f"Profile timer did not sample exactly one MEAN operation in {path}")
            require(data["output"] == reference["output"], f"Profile output differs from frozen performance run in {path}")
            require((data["arena_cap"], data["arena_used"]) == (reference["arena_cap"], reference["arena_used"]),
                    f"Profile tensor allocation differs from frozen performance run in {path}")
            profile_us, profile_cycles, mean_us, mean_cycles, _ = zip(*(p[1:] for p in profile))
            empty_us, empty_cycles = zip(*(c[1:] for c in calibration))
            overhead_us, overhead_cycles = statistics.median(empty_us), statistics.median(empty_cycles)
            boots.append({**data, "profile_us": profile_us, "profile_cycles": profile_cycles,
                          "mean_us_raw": mean_us, "mean_cycles_raw": mean_cycles,
                          "empty_us": empty_us, "empty_cycles": empty_cycles,
                          "mean_us_adjusted": [sample - overhead_us for sample in mean_us],
                          "mean_cycles_adjusted": [sample - overhead_cycles for sample in mean_cycles],
                          "paired_timer_delta_us": [a - b for a, b in zip(profile_us, data["us"])],
                          "paired_timer_delta_cycles": [a - b for a, b in zip(profile_cycles, data["cycles"])],
                          "outside_mean_us": [a - b for a, b in zip(profile_us, mean_us)],
                          "outside_mean_cycles": [a - b for a, b in zip(profile_cycles, mean_cycles)]})
        by_variant[variant] = {"boots": boots}
    stock = by_variant["stock"]["boots"]
    for variant, item in by_variant.items():
        boots = item["boots"]
        keys = ("us", "cycles", "profile_us", "profile_cycles", "mean_us_raw", "mean_cycles_raw", "empty_us",
                "empty_cycles", "mean_us_adjusted", "mean_cycles_adjusted", "paired_timer_delta_us",
                "paired_timer_delta_cycles", "outside_mean_us", "outside_mean_cycles")
        item["medians"] = {key: boot_median(boots, key) for key in keys}
        item["mean_cycle_share_pct"] = 100 * item["medians"]["mean_cycles_adjusted"] / item["medians"]["cycles"]
        item["mean_time_share_pct"] = 100 * item["medians"]["mean_us_adjusted"] / item["medians"]["us"]
        item["mean_cycle_speedup"] = boot_median(stock, "mean_cycles_adjusted") / item["medians"]["mean_cycles_adjusted"]
        item["mean_time_speedup"] = boot_median(stock, "mean_us_adjusted") / item["medians"]["mean_us_adjusted"]
        item["mean_cycle_reduction_pct"] = 100 * (1 - 1 / item["mean_cycle_speedup"])
        item["mean_time_reduction_pct"] = 100 * (1 - 1 / item["mean_time_speedup"])
    return {"variants": by_variant, "staged_hashes": sources,
            "common_compile_units": compare_compile_flags(directory)}


def validate_new_full(model):
    directory = EXT / "results/full" / model
    sources = verify_staged_sources(directory, VARIANTS, "{variant}-staged-source.sha256")
    for filename in ("mean_bridge.cc", "mean_bridge.h"):
        require(sources[filename] == digest((KIT / "integration" / filename).read_bytes()),
                f"Full timing differs from the original adapter in {model}")
    preflight = json.loads((model_dir(model) / "preflight.json").read_text())
    require(not preflight["pools"] and len(preflight["means"]) == 1, f"Wrong graph for {model}")
    require(sources["model.tflite"] == preflight["model_sha256"] and sources["input.bin"] == preflight["input_sha256"],
            f"Model or input never reached {model} firmware")
    by_variant = {}
    for variant in VARIANTS:
        boots = []
        for boot in (1, 2):
            path = directory / f"{variant}-{boot}.log"
            content, parsed = timed_capture(path)
            require("CNN_PROFILE" not in content and "CNN_CASE" not in content, f"Timing contains instrumentation: {path}")
            boots.append(parsed)
        require(boots[0]["app_image_bytes"] == boots[1]["app_image_bytes"], f"Image size changes between {model} boots")
        by_variant[variant] = boots
    require(len({b["output"] for bb in by_variant.values() for b in bb}) == 1, f"Output mismatch for {model}")
    require(len({(b["arena_cap"], b["arena_used"]) for bb in by_variant.values() for b in bb}) == 1,
            f"Different tensor allocations for {model}")
    stock = by_variant["stock"]
    comparisons = {}
    for variant, boots in by_variant.items():
        elapsed = boot_median(boots, "us")
        cycles = boot_median(boots, "cycles")
        reduction = 100 * (1 - elapsed / boot_median(stock, "us"))
        paired = [100 * (1 - statistics.median(b["us"]) / statistics.median(s["us"])) for b, s in zip(boots, stock)]
        threshold = "WIN" if reduction > 1 else "LOSS" if reduction < -1 else "NEUTRAL"
        verdict = threshold
        if variant == "stock":
            verdict = "BASELINE"
        elif variant == "opt2":
            verdict = "CONTROL ONLY"
        elif (verdict == "WIN" and min(paired) <= 0) or (verdict == "LOSS" and max(paired) >= 0):
            verdict = "INCONCLUSIVE"
        comparisons[variant] = {"model": model, "variant": variant, "median_us": elapsed,
            "median_cycles": cycles, "time_speedup": boot_median(stock, "us") / elapsed,
            "cycle_speedup": boot_median(stock, "cycles") / cycles, "time_reduction_pct": reduction,
            "numerical_threshold": threshold, "verdict": verdict,
            "boot_time_reductions_pct": paired,
            "min_us": min(min(b["us"]) for b in boots), "max_us": max(max(b["us"]) for b in boots),
            "min_cycles": min(min(b["cycles"]) for b in boots), "max_cycles": max(max(b["cycles"]) for b in boots),
            "arena_used": boots[0]["arena_used"], "arena_cap": boots[0]["arena_cap"],
            "app_image_bytes": boots[0]["app_image_bytes"],
            "stack_high_water_bytes": min(b["stack_high_water_bytes"] for b in boots),
            "all_outputs_equal": True, "samples": sum(len(b["us"]) for b in boots)}
    return {"raw": by_variant, "comparisons": comparisons, "graph": preflight,
            "qacc_verified": True, "sliding_calls_by_pool": [], "staged_hashes": sources,
            "common_compile_units": compare_compile_flags(directory)}


def write_csv(path, rows):
    with path.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--correctness-only", nargs="+", choices=QACC_MODELS)
    args = parser.parse_args()
    graphs = json.loads((EXT / "models/mean_graphs.json").read_text())
    names = args.correctness_only or QACC_MODELS
    correctness = {model: validate_correctness(model, graphs[model]) for model in names}
    if args.correctness_only:
        for name, value in correctness.items():
            print(name, "PASS", value["inputs"], "extra inputs × 4 builds")
        return
    new_full = {model: validate_new_full(model) for model in NEW_MODELS}
    full = {**ORIGINAL, **new_full}
    profile = {}
    for model in QACC_MODELS:
        reference = full[model]["raw"]["stock"][0]
        profile[model] = validate_profile(model, reference)
        versions = full[model]["comparisons"]
        require(all(versions[v]["all_outputs_equal"] for v in VARIANTS), f"Different frozen output in {model}")
    output = EXT / "results/analysis"
    output.mkdir(parents=True, exist_ok=True)
    (output / "compare.json").write_text(json.dumps({"full": full, "mean_shapes": graphs,
                         "profile": profile, "extra_correctness": correctness}, indent=2) + "\n")
    full_rows = []
    for model, item in full.items():
        for variant, v in item["comparisons"].items():
            full_rows.append({"model": model, "variant": variant, "source": "original" if model in ORIGINAL else "extension",
                **{key: v[key] for key in ("median_us", "median_cycles", "time_speedup", "cycle_speedup",
                   "time_reduction_pct", "min_us", "max_us", "min_cycles", "max_cycles", "numerical_threshold",
                   "verdict", "arena_used", "arena_cap", "app_image_bytes", "stack_high_water_bytes",
                   "all_outputs_equal", "samples")},
                "qacc_executed": item["qacc_verified"] and variant in ("mean", "combined"),
                "sliding_executed": any(item["sliding_calls_by_pool"]) and variant in ("opt2", "combined")})
    write_csv(output / "compare.csv", full_rows)
    full_samples = []
    for model, item in full.items():
        for variant, boots in item["raw"].items():
            for boot, data in enumerate(boots, start=1):
                for index, (us, cycles) in enumerate(zip(data["us"], data["cycles"])):
                    full_samples.append({"model": model, "variant": variant, "boot": boot, "index": index,
                                         "us": us, "cycles": cycles})
    write_csv(output / "full_samples.csv", full_samples)
    profile_rows = []
    profile_samples = []
    for model, item in profile.items():
        for variant, value in item["variants"].items():
            profile_rows.append({"model": model, "variant": variant,
                "mean_shape": "x".join(map(str, graphs[model]["input_shape"][1:])), **value["medians"],
                **{key: value[key] for key in ("mean_cycle_share_pct", "mean_time_share_pct", "mean_cycle_speedup",
                   "mean_time_speedup", "mean_cycle_reduction_pct", "mean_time_reduction_pct")}})
            for boot, data in enumerate(value["boots"], start=1):
                for index in range(len(data["us"])):
                    profile_samples.append({"model": model, "variant": variant, "boot": boot, "index": index,
                                            **{key: data[key][index] for key in value["medians"]}})
    write_csv(output / "mean_profile.csv", profile_rows)
    write_csv(output / "mean_profile_samples.csv", profile_samples)
    print("PASS", len(full), "full CNNs,", len(profile), "MEAN profiles,", sum(m["inputs"] for m in correctness.values()),
          "extra inputs across four builds")


if __name__ == "__main__":
    main()
