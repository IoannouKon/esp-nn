#!/usr/bin/env python3
"""Check same-group timed image inputs and collect linked section sizes."""
import json
from pathlib import Path
import re
import subprocess

results = Path(__file__).resolve().parents[1] / "results"
variants = ("stock", "opt2", "mean", "combined")
groups = {
    "core": "mnist_fixed max3 max5 mean_only both depthwise_both avg_control neutral_control person_detection".split(),
    "mobiles": ["mobilenet_v2", "mobilenet_v3_small"],
    "lite0": ["efficientnet_lite0"],
}
manifest = json.loads((results / "manifest.json").read_text())
report = ["# Firmware sizes and reproducibility checks", "",
          "Each group links its own immutable model bundle. Section sizes are from the archived timed ELF. "
          "Sizes between variants should be compared within one group.", "",
          "| Group | Variant | Flash image | Δ vs stock | Flash text | Flash rodata | IRAM text | DRAM data | DRAM BSS |",
          "|---|---|---:|---:|---:|---:|---:|---:|---:|"]
summary = {}
for group, models in groups.items():
    evidence = {}
    for variant in variants:
        folder = results / "build" / f"{group}-{variant}-build"
        path = folder / "evidence.json"
        if path.exists():
            evidence[variant] = (folder, json.loads(path.read_text()))
    if len(evidence) != 4:
        continue
    assert len({e["sdkconfig_sha256"] for _, e in evidence.values()}) == 1, group
    assert len({json.dumps(e["app_sources"], sort_keys=True) for _, e in evidence.values()}) == 1, group
    stock_size = evidence["stock"][1]["firmware_bytes"]
    kernels = {v: e["kernel_sources"] for v, (_, e) in evidence.items()}
    for path, h in kernels["stock"].items():
        if "max_pool" in path:
            assert kernels["mean"][path] == h and kernels["combined"][path] == kernels["opt2"][path]
        else:
            assert kernels["opt2"][path] == h and kernels["combined"][path] == kernels["mean"][path]
    summary[group] = {}
    for variant, (folder, meta) in evidence.items():
        for i, name in enumerate(models):
            for kind, ext in (("model", "tflite"), ("input", "bin")):
                blob = meta["firmware_blobs"][f"{kind}_{i}.{ext}"]
                assert blob["embedded"] and manifest[name][f"{kind}_sha256"] == blob["sha256"], (group, variant, name)
        syms = (folder / "symbols.txt").read_text()
        assert "__wrap_esp_nn_" not in syms
        assert "esp_nn_max_pool_s8_esp32s3" in syms and "esp_nn_mean_nhwc_s8_esp32s3" in syms
        assert ("esp_nn_max_pool_s8_esp32s3_sliding_row_asm" in syms) == (variant in ("opt2", "combined"))
        assert ("esp_nn_mean_s8_16ch_qacc" in syms) == (variant in ("mean", "combined"))
        fingerprints = {}
        for boot in (1, 2):
            log = results / "logs" / f"suite_{group}" / f"{variant}-{boot}.log"
            if log.exists() and "CNN_SUITE_DONE" in log.read_text(errors="replace"):
                raw = log.read_text(errors="replace")
                prefixes = re.findall(r"ELF file SHA256:\s+([a-f0-9]+)", raw)
                assert prefixes and all(meta["elf_sha256"].startswith(s) for s in prefixes), log
                assert "cpu freq: 240000000 Hz" in raw and "psram_bytes=8388608 mode=timed" in raw, log
                fingerprints[boot] = prefixes[-1]
        elf = folder / "espnn_multi_cnn.elf"
        raw = subprocess.check_output(["xtensa-esp32s3-elf-objdump", "-h", str(elf)], text=True)
        sizes = {k: int(v, 16) for k, v in re.findall(r"^\s*\d+\s+(\S+)\s+([\da-f]+)", raw, re.M)}
        keys = [".flash.text", ".flash.rodata", ".iram0.text", ".dram0.data", ".dram0.bss"]
        summary[group][variant] = {"flash_image": meta["firmware_bytes"], "sdkconfig_sha256": meta["sdkconfig_sha256"],
                                   "section_bytes": {k: sizes.get(k, 0) for k in keys},
                                   "boot_elf_sha256_prefixes": fingerprints}
        report.append(f"| {group} | {variant} | {meta['firmware_bytes']} | {meta['firmware_bytes']-stock_size:+} | "
                      + " | ".join(str(sizes.get(k, 0)) for k in keys) + " |")
report += ["", "Each published row belongs to a group whose four SDK configs and app-source hashes match. "
           "The check verifies the complete model and input bytes are embedded in each binary. "
           "Linked symbols match the respective kernel variants and contain no diagnostic wrappers. Serial ELF fingerprints match the archived image whenever a capture has completed.", ""]
(results / "firmware_sizes.md").write_text("\n".join(report))
(results / "firmware_sizes.json").write_text(json.dumps(summary, indent=2) + "\n")
