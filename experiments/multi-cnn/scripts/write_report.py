#!/usr/bin/env python3
"""Render the report from qualified captures and build provenance."""
from collections import Counter
from pathlib import Path
import json

root = Path(__file__).resolve().parents[1]
results = root / "results"
data = json.loads((results / "comparison.json").read_text())
manifest = json.loads((results / "manifest.json").read_text())
accuracy_file = results / "cifar_int8_accuracy.json"
accuracy = json.loads(accuracy_file.read_text()) if accuracy_file.exists() else {}
versions = ("stock", "opt2", "mean", "combined")
comparisons = (("stock", "opt2"), ("stock", "mean"), ("stock", "combined"),
               ("opt2", "combined"), ("mean", "combined"))

def pretty(x):
    return f"{x:g}" if x is not None else "—"

lines = ["# ESP32-S3-EYE multi-CNN benchmark", "",
    "Four ESP-NN builds share the same pinned ESP-TFLite Micro runtime, guarded MEAN adapter and frozen model inputs. "
    "Stock uses Espressif's optimized ESP32-S3 ESP-NN integration, including the stock max-pool and mean routines.",
    "", "## Overall outcomes", "",
    "| Comparison | WIN | LOSS | NEUTRAL | SKIP | INCONCLUSIVE |",
    "|---|---:|---:|---:|---:|---:|"]
complete_models = [m for m in data["models"].values() if m["exact_outputs"] is not None]
exact_models = sum(m["exact_outputs"] for m in complete_models)
samples = sum(len(r["times_us"]) for m in complete_models
              for f in m["firmwares"].values() for r in f["runs"] if r["valid"])
lines[6:6] = [
    f"{len(complete_models)} of {len(data['models'])} models completed all eight qualified physical timing boots. "
    f"These models contributed {samples:,} timed inferences. "
    f"Full fixed-input outputs matched across all four variants for {exact_models} models.", ""]
for a, b in comparisons:
    counts = Counter(r["verdict"] for r in data["comparisons"] if (r["baseline"], r["candidate"]) == (a, b))
    vals = " | ".join(str(counts[k]) for k in ["WIN", "LOSS", "NEUTRAL", "SKIP", "INCONCLUSIVE"])
    lines.append(f"| {a} → {b} | {vals} |")
lines += ["", "## Invoke medians and actual dispatch", "",
    "Times are microseconds. Each qualified cell uses two physical boots, five untimed warm-ups and 30 timed "
    "Invoke calls per boot. The reported value is the median of the two per-boot medians. The model input is "
    "identical on each timed inference. Dispatch counts come from separate Combined diagnostic boots. "
    "QACC helper counts include the reference comparison and synthetic-pattern trials.", "",
    "| Model | Stock | Opt1+Opt2 | EXP-MEAN | Combined | Sliding assembly calls | QACC calls¹ | Complete output |",
    "|---|---:|---:|---:|---:|---:|---:|---|"]
for name, m in data["models"].items():
    med = " | ".join(pretty(m["firmwares"][v]["median_us"]) for v in versions)
    d = m["dispatch"]
    out = "exact" if m["exact_outputs"] else "mismatch" if m["exact_outputs"] is False else "unqualified"
    lines.append(f"| {name} | {med} | {d['sliding_rows']} | {d['qacc_blocks']} | {out} |")
lines += ["", "¹ A supported 32-channel MEAN invokes two 16-lane blocks in an ordinary inference. The diagnostic reported 14 calls per MEAN layer because it also ran six comparison patterns. Each of the three MEAN tensors matched both TFLite Micro reference routes in all six comparisons.", "",
    "## All model comparisons", "",
    "A time reduction greater than 1% crosses the WIN threshold; a time increase greater than 1% crosses the LOSS "
    "threshold. The verdict also checks whether the targeted path ran and whether the paired boot medians "
    "agree on the direction. Two boots describe the observed spread.", "",
    "| Model | Comparison | Speedup | Time reduction | Threshold | Verdict | Notes |",
    "|---|---|---:|---:|---|---|---|"]
for r in data["comparisons"]:
    su = f"{r['speedup']:.4f}×" if r["speedup"] is not None else "—"
    pct = f"{r['reduction_pct']:+.3f}%" if r["reduction_pct"] is not None else "—"
    lines.append(f"| {r['model']} | {r['baseline']} → {r['candidate']} | {su} | {pct} | "
                 f"{r['threshold'] or '—'} | {r['verdict']} | {r['note'] or ''} |")
lines += ["", "## Boot variation and arena usage", "",
    "Each boot entry is median [minimum, maximum] in microseconds. Extra inputs are checked outside the timing loop. "
    "The JSON includes every individual measurement and complete output tensor.", "",
    "| Model | Firmware | Boot 1 | Boot 2 | PSRAM arena use, bytes |",
    "|---|---|---|---|---:|"]
for name, m in data["models"].items():
    for variant, va in m["firmwares"].items():
        b = {r["boot_index"]: r for r in va["runs"]}
        if not b:
            continue
        def detail(i):
            r = b.get(i)
            if not r:
                return "—"
            return f"{pretty(r['median_us'])} [{pretty(r['min_us'])}, {pretty(r['max_us'])}]"
        used = sorted({r["arena_used"] for r in b.values() if r["arena_used"] is not None})
        lines.append(f"| {name} | {variant} | {detail(1)} | {detail(2)} | {', '.join(map(str, used)) or '—'} |")
lines += ["", "## Model and output inventory", "",
    "| Model | Input → output | MAX_POOL / MEAN | Host INT8 top-1¹ | Extra board inputs | Desktop reference exact² |",
    "|---|---|---:|---:|---:|---:|"]
for name, m in manifest.items():
    r = data["models"][name]
    ins, out = m["input"], m["output"]
    dims = f"{ins['dtype']} {ins['shape']} → {out['dtype']} {out['shape']}"
    pools = m["operator_counts"].get("MAX_POOL_2D", 0)
    means = m["operator_counts"].get("MEAN", 0)
    acc = f"{100*accuracy[name]['top1']:.1f}%" if name in accuracy else "—"
    host = r["host_reference_matches"]
    host_text = f"{host}/{1+r['validation_count']}" if host is not None else "—"
    lines.append(f"| {name} | {dims} | {pools} / {means} | {acc} | {r['validation_count']} | "
                 f"{host_text} |")
different = [(name, m["host_reference_fixed_diff"]) for name, m in data["models"].items()
             if m["host_reference_fixed_diff"] and m["host_reference_fixed_diff"]["mismatched_elements"]]
if different:
    lines += ["", "Desktop-versus-board fixed-input differences in quantized output units", ""]
    for name, diff in different:
        default = data["models"][name]["host_default_fixed_diff"]
        host_default = (f" Desktop default: {default['mismatched_elements']} elements, max "
                        f"{default['max_abs_difference']}." if default else "")
        lines.append(f"- {name} — Desktop reference: {diff['mismatched_elements']} elements, max "
                     f"{diff['max_abs_difference']}." + host_default)
lines += ["", "¹ Custom CIFAR-10 models were trained for one epoch using the kit defaults. This is desktop TFLite classification "
    "using actual INT8 logits on the first 1,000 held-out test images. It is distinct from board correctness.",
    "", "² Desktop TFLite BUILTIN_REF and ESP-TFLite Micro may use different integer convolution and reduction paths. "
    "The board-to-board gate compares all output bytes. The on-board MEAN test compares its actual intermediates "
    "directly with the pinned TFLite Micro reference and original registration.", "",
    "Person Detection's original model was rejected by the desktop TFLite importer's affine quantization check "
    "for several legacy bias tensors. Its untouched firmware model is checked on ESP-TFLite Micro.",
    "", "The MobileNetV3-Small artifact is the public historical INT8 channelwise release. The provider withdrew "
    "that export after finding accuracy degradation. Treat its result as a timing observation on a known "
    "architecture. The exported graph uses average pooling and has no MEAN or MAX_POOL_2D nodes.", "",
    "## Evidence", "",
    "- [Operator versions, provenance, tensor shapes and SHA256 hashes](manifest.json)",
    "- [Individual measurements and exact output bytes](comparison.json)",
    "- [All comparisons as CSV](comparison.csv)",
    "- [Raw serial and flash logs](logs/)",
    "- [Build and configuration evidence](build_provenance.md) and [firmware sizes](firmware_sizes.md)",
    "- [MEAN integration source and reference arithmetic](mean_bridge_patch/README.md)",
    "- [MobileNetV3-Small artifact](https://huggingface.co/litert-community/MobileNet-v3-small/commit/77f13855abb1d843015ff3605e5748b960ffe7dd) and [upstream accuracy finding](https://huggingface.co/litert-community/MobileNet-v3-small/commit/16a1a16018be8bf3db791b816387563f2204d756)",
]
ref_path = results / "diagnostics" / "stock_tflm_reference_results.json"
if ref_path.exists():
    ref = json.loads(ref_path.read_text())
    v3 = ref["mobilenet_v3_small"]
    d = v3["stock_optimized_board_vs_board_reference"]
    at = lines.index("## Evidence")
    lines[at:at] = [
        "## Untimed MobileNet fidelity check", "",
        "A separate on-board diagnostic compiled out ESP-NN calls guarded by the pinned TFLite Micro runtime. "
        "It reused the identical models and fixed inputs. The slow reference invokes completed after nonfatal idle-task "
        "watchdog reports, which are confined to this diagnostic log.", "",
        "MobileNetV2's 1,000 output bytes matched the optimized stock board output exactly. "
        "Its fixed-input difference from desktop default TFLite was at most four quantized units.", "",
        f"MobileNetV3-Small saturated {v3['saturated_elements_stock']} of 1,000 logits in optimized stock "
        f"and {v3['saturated_elements_board_reference']} of 1,000 in the reference diagnostic. "
        f"The two on-board routes differed at {d['mismatched_elements']} logits, with a maximum absolute difference "
        f"of {d['max_abs_difference']} quantized units. The underlying operator fault was not isolated. "
        "All four timed outputs agreed with each other, and neither study optimization was called by that graph. "
        "This timing control therefore gives no evidence of MobileNetV3-Small classification fidelity.", "",
        "[Complete reference serial log](logs/suite_mobiles/tflm-reference-diagnostic.log) · "
        "[Exact comparison data](diagnostics/stock_tflm_reference_results.json)", "",
    ]
summary = results / "conclusions.md"
if summary.exists():
    lines[2:2] = [summary.read_text().strip(), ""]
(results / "CNN_RESULTS.md").write_text("\n".join(lines) + "\n")
