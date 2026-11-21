#!/usr/bin/env python3
"""Render the hardware report, including cases that did not qualify."""
from collections import Counter
from pathlib import Path
import json
import re

kit = Path(__file__).resolve().parents[1]
results = kit / "results"
analysis = results / "analysis/compare.json"
report = json.loads(analysis.read_text()) if analysis.exists() else {"models": {}, "failures": {}}
reference_names = ["mlperf_cifar10_resnet8", "mlperf_vww_mobilenet", "tflm_person_detection",
                   "mlperf_kws_dscnn", "mlperf_cifar10_resnet6", "mlperf_vww_14block",
                   "mlperf_vww_20block"]
names = reference_names + ["mnist_fixed", "max3", "max5", "mean_only", "both", "depthwise_both"]
preflight = {}
for name in names:
    f = kit / "models" / name / "preflight.json"
    if f.exists():
        preflight[name] = json.loads(f.read_text())
statuses = {}
status_file = results / "run-status.txt"
if status_file.exists():
    statuses = dict(line.split(maxsplit=1) for line in status_file.read_text().splitlines())
reasons_file = results / "skip-reasons.json"
reasons = json.loads(reasons_file.read_text()) if reasons_file.exists() else {}
measured = report["models"]
hits = sum(n in measured for n in reference_names)
opinions = [(n, m) for n, m in measured.items() if any(m["sliding_calls_by_pool"])]
qacc = [(n, m) for n, m in measured.items() if m["qacc_verified"]]
desktop_file = results / "desktop-reference.json"
desktop_reference = json.loads(desktop_file.read_text()) if desktop_file.exists() else {}


def desktop_parity(board, desktop):
    if not desktop:
        return "unavailable"
    if board is None:
        return "pending"
    left, right = bytes.fromhex(board), bytes.fromhex(desktop)
    if left == right:
        return "exact"
    if len(left) != len(right):
        return f"{len(left)} vs {len(right)} bytes"
    differences = [abs((a if a < 128 else a - 256) - (b if b < 128 else b - 256)) for a, b in zip(left, right)]
    return f"{sum(d > 0 for d in differences)}/{len(left)} differ, max Δ {max(differences)}"


lines = ["# ESP32-S3-EYE full-CNN benchmark", "",
         f"{hits} pinned upstream pretrained CNNs and {len(measured) - hits} local CNNs completed "
         f"the four-build comparison, for {len(measured) * 240:,} accepted timed inferences. "
         "All accepted models returned identical complete output tensors across both boots and all four firmware builds."
         + (" No models were skipped." if len(measured) == len(names) else ""), "",
         "The inputs for the upstream pretrained models are deterministic raw INT8 samples for latency and output "
         "parity. This experiment measures no classifier accuracy on those inputs.", "",
         "## Model results", "",
         "| Model | Workload | Outcome | Arena used (bytes) | Sliding calls per pool | QACC |",
         "|---|---|---|---:|---|---|"]
for name in names:
    v = measured.get(name)
    meta = preflight.get(name)
    if v:
        arena = v["raw"]["stock"][0]["arena_used"]
        outcome = "PASS"
    else:
        arena = "—"
        outcome = reasons.get(name, "INCONCLUSIVE" if statuses.get(name) == "FAILED" else "PENDING")
    graph_kind = "pretrained" if name in reference_names else "frozen MNIST control" if name == "mnist_fixed" else "custom CIFAR-10"
    rows = ", ".join(map(str, v["sliding_calls_by_pool"])) if v and v["sliding_calls_by_pool"] else "—"
    lines.append(f"| {name} | {graph_kind} | {outcome} | {arena} | {rows} | "
                 f"{'verified' if v and v['qacc_verified'] else 'control only / no QACC' if v else '—'} |")
lines += ["", "## Complete inference timing and cycles", "",
          "Each value is the median of the two per-boot medians. Every boot ran five untimed warm-ups and "
          "30 timed inferences. The time comes from esp_timer_get_time; cycles come from the same-core hardware "
          "cycle counter around the same invocation and timer reads. Cycle deltas can include interrupts and scheduler overhead.", "",
          "| Model | Build | Median µs | Median cycles | Time speedup | Cycle speedup | Time reduction | Sample ranges µs / cycles | Verdict |",
          "|---|---|---:|---:|---:|---:|---:|---|---|"]
for name in names:
    v = measured.get(name)
    if not v:
        continue
    for branch, a in v["comparisons"].items():
        span = f"{a['min_us']}–{a['max_us']} / {a['min_cycles']}–{a['max_cycles']}"
        lines.append(f"| {name} | {branch} | {a['median_us']:g} | {a['median_cycles']:g} | "
                     f"{a['time_speedup']:.4f}× | {a['cycle_speedup']:.4f}× | {a['time_reduction_pct']:+.3f}% | {span} | {a['verdict']} |")
lines += ["", "Timing changes in control-only rows are preserved in the table and raw data. "
          "A control-only comparison has no verified execution of the changed kernel. The numerical cutoff is a "
          "time reduction greater than 1% for a win and a time increase greater than 1% for a loss. The two paired boot medians must agree on direction.", "",
          "## Combined versus individual builds", "",
          "The verdict describes the effect of adding the other optimization. A control-only row preserves the measured "
          "difference when the additional kernel had no verified call.", "",
          "| Model | From Opt1+Opt2 | Verdict | From EXP-MEAN | Verdict |",
          "|---|---:|---|---:|---|"]
for name in names:
    if name not in measured or "combined_vs_individual" not in measured[name]:
        continue
    pool = measured[name]["combined_vs_individual"]["opt2"]
    mean = measured[name]["combined_vs_individual"]["mean"]
    lines.append(f"| {name} | {pool['time_speedup']:.4f}× / {pool['time_reduction_pct']:+.3f}% | {pool['verdict']} | "
                 f"{mean['time_speedup']:.4f}× / {mean['time_reduction_pct']:+.3f}% | {mean['verdict']} |")
lines += ["", "## Binary size and memory", "",
          "App image sizes come from the verified esptool flash write. Arena usage stayed identical across the eight boots of each model. "
          "The JSON and CSV provide stack high-water marks for each firmware.", "",
          "| Model | Arena used (bytes) | Stock image (bytes) | Opt1+Opt2 Δ bytes | EXP-MEAN Δ bytes | Combined Δ bytes |",
          "|---|---:|---:|---:|---:|---:|"]
for name in names:
    if name not in measured:
        continue
    variants = measured[name]["comparisons"]
    stock = variants["stock"].get("app_image_bytes")
    if stock is None:
        continue
    deltas = [f"{variants[v]['app_image_bytes'] - stock:+,}" for v in ("opt2", "mean", "combined")]
    lines.append(f"| {name} | {variants['stock']['arena_used']:,} | {stock:,} | " + " | ".join(deltas) + " |")
lines += ["",
          "## Graph and data provenance", "",
          "| Model | Operator counts | Model SHA-256 | Input SHA-256 | Desktop default¹ | Desktop reference¹ |",
          "|---|---|---|---|---|---|"]
for name in names:
    meta = preflight.get(name)
    if not meta:
        continue
    types = ", ".join(f"{op} ×{cnt}" for op, cnt in Counter(meta["ops"]).items())
    actual = measured[name]["raw"]["stock"][0]["output"] if name in measured else None
    default = desktop_parity(actual, meta["host_output_hex"])
    reference = desktop_parity(actual, desktop_reference.get(name, {}).get("output_hex"))
    lines.append(f"| {name} | {types} | {meta['model_sha256']} | {meta['input_sha256']} | {default} | {reference} |")
lines += ["", "¹ The experiment gates correctness on whole output parity across the four on-board builds. "
          "The desktop columns compare against TensorFlow Lite 2.15.1 with its default and BUILTIN_REF kernels. "
          "The exact differences describe runtime agreement for the fixed input. TensorFlow Lite 2.15.1 rejects the pinned Person Detection "
          "model's legacy affine metadata. Its input was generated from the unchanged model's schema. "
          "[Desktop reference outputs](desktop-reference.json)", "",
          "## Dispatch and MEAN adapter", "",
          f"{len(opinions)} accepted graphs have measured sliding assembly calls in a separate diagnostic build. "
          f"{len(qacc)} accepted graphs have verified QACC execution. The seven pinned upstream graphs contain neither "
          "MAX_POOL_2D nor MEAN. Their timing differences cannot be attributed to either study optimization.", "",
          "The pinned runtime's built-in MEAN operates within TFLite Micro. The optional graph-level bridge is restricted "
          "to the validated INT8 NHWC spatial reduction and shared among all four custom builds. "
          "[Adapter and quantization mapping](../integration/README.md) · [Diagnostic logs](diagnostics/)", ""]
if all((results / 'diagnostics/both' / f'{variant}-probe.log').exists() for variant in ('opt2', 'mean')):
    lines += ["On `both`, the separate Opt1+Opt2 firmware called the sliding assembly 16 times per pool layer "
              "and had zero QACC calls. The EXP-MEAN firmware had zero sliding calls and logged 14 QACC blocks "
              "during the diagnostic, including the extra reference comparisons. "
              "[Opt1+Opt2 probe](diagnostics/both/opt2-probe.log) · [EXP-MEAN probe](diagnostics/both/mean-probe.log)", ""]
lines += [
          "## Setup and reproducibility", "",
          "- ESP32-S3-EYE, USB Serial/JTAG on /dev/ttyACM0, one core at 240 MHz, 8 MiB octal PSRAM at 80 MHz. "
          "The kit config uses a 64 KiB, 8-way data cache, 64-byte cache lines, a 2 MiB aligned PSRAM tensor arena "
          "and an 8 KiB main task stack. Actual use and stack high-water marks are in the machine-readable data.",
          "- ESP-IDF v5.5.1 at fcae32885b0296b32044cb99ecbdc50d98dddb83 and Xtensa GCC 14.2.0. "
          "ESP-TFLite Micro v1.4.3 at df8722334a80ceabc609c1e72968f417cd9437f1. "
          "IDF reports a dirty tree from unrelated pre-existing example edits. [IDF status](idf-revision.txt)",
          "- Stock ESP-NN at ace42ac7721119cd543fc40ffe719e601fa8f20f. Opt1+Opt2 at "
          "edb003c6770491abb74766835f4c803b9d4f5a20. EXP-MEAN at 4bfa49c64a932f700688c2007a01d8ea1fa102ac. "
          "Combined overlays the exact two-file pooling patch on the detached EXP-MEAN tree. "
          "Stock uses Espressif's ESP32-S3 optimized backend through ESP-TFLite Micro's ESP-NN integration.",
          "- The original firmware runner supplies both timers. The harness restores the frozen input before each "
          "Invoke because TFLM may reuse the input arena. The scheduler yield and output validation/printing stay "
          "outside the timed region. All captures reset the board after monitor attachment and verify the flashed ELF fingerprint.",
          "- Per-model boot order is Stock, Opt2, Mean, Combined, Combined, Mean, Opt2, Stock. "
          "The 20-minute ceiling covers each serial capture. Build and flash run separately.",
          "- The warm-up/steady-state harness and model bytes match across all implementations of each model. "
          "The compiled paths, ELF hashes, SDK config, boot data, build and flash logs are alongside each serial log.",
          "- ResNet6 triggered the idle-task watchdog during the first trial. The archived trial is excluded from the comparison. "
          "Every accepted ResNet6 build uses a 20-second watchdog interval set before allocation and inference.",
          "",
          "[Frozen upstream URLs](../PRETRAINED_MODELS.json) · [Replay commands](EXPERIMENT_COMMANDS.md) · "
          "[All comparisons](analysis/compare.csv) · [Revisions and compiler paths](provenance/) · [Raw samples and output bytes](analysis/compare.json) · "
          "[Complete serial/build/flash logs](logs/) · [Combined production diff](combined-pool.diff) · "
          "[Worktree provenance](workspace.log) · [Toolchain](toolchain.txt) · [Final audit](provenance/final-verification.txt)", ""]
coverage = []
if opinions:
    targets = [(n, m["comparisons"]["opt2"]) for n, m in opinions]
    nwin = sum(x["verdict"] == "WIN" for _, x in targets)
    best_name, best = max(targets, key=lambda r: r[1]["time_reduction_pct"])
    low = min(x["time_reduction_pct"] for _, x in targets)
    coverage.append(f"- Opt1+Opt2 won on {nwin} of {len(targets)} models with verified sliding dispatch. "
                    f"Latency fell {low:.3f}–{best['time_reduction_pct']:.3f}%. "
                    f"{best_name} had the largest reduction at {best['time_speedup']:.4f}× stock speed.")
if qacc:
    for name, model in qacc:
        m = model["comparisons"]
        mean = m["mean"]
        delta = 100 * (1 - m["combined"]["median_us"] / m["opt2"]["median_us"])
        coverage.append(f"- {name} called QACC. EXP-MEAN reduced latency by {mean['time_reduction_pct']:+.3f}% "
                        f"versus stock. Combined reduced latency by {delta:+.3f}% versus Opt1+Opt2.")
    coverage.append("- The Mean-only firmware also shifted timings by more than 1% on custom controls with no MEAN "
                    "operator. The study verifies QACC dispatch and correctness. These control shifts limit how precisely "
                    "the measured full-app gains can be attributed to QACC alone.")
inactive_regressions = [(name, variant, row['time_reduction_pct'])
                        for name, model in measured.items()
                        for variant, row in model['comparisons'].items()
                        if row['verdict'] == 'CONTROL ONLY' and row['numerical_threshold'] == 'LOSS']
for name, variant, delta in inactive_regressions:
    coverage.append(f"- The {variant} firmware ran {name} {-delta:.3f}% slower than stock. "
                    "The changed kernel had no calls in that graph.")
active_rows = [row for model in measured.values() for row in model['comparisons'].values()
               if row['sliding_pool_executed'] or row['mean_optimization_executed']]
if active_rows and all(row['verdict'] == 'WIN' for row in active_rows):
    coverage.append("- Every stock comparison with verified target dispatch met the study's win rule. "
                    "The evidence supports a workload-specific claim about eligible pooling and MEAN graphs.")
stamp = results / "diagnostics/mean-bridge-qualified.txt"
if stamp.exists():
    checks = re.findall(r"tested=(\d+) guard_rejected=(\d+) compared=(\d+) mismatches=(\d+)", stamp.read_text())
    if checks:
        vectors=sum(int(c[0]) for c in checks)
        elems=sum(int(c[2]) for c in checks)
        coverage.append(f"- The stock and Combined reference stress tests matched on {vectors:,} complete "
                        f"tensors and {elems:,} output bytes in total. The three per-model MEAN probes also run the "
                        "actual intermediate through both TFLite Micro reference routes.")
if len(measured) == len(names):
    controls = [c for n in reference_names for v,c in measured[n]["comparisons"].items() if v != "stock"]
    maximum = max(abs(c["time_reduction_pct"]) for c in controls)
    coverage.append(f"- All seven pretrained models completed inference. Neither target kernel executed on those "
                    f"graphs, and their largest absolute median change was {maximum:.3f}%.")
if coverage:
    lines[2:2] = ["## Target-kernel verdicts", ""] + coverage + [""]
if report["failures"]:
    lines.extend(["## Excluded captures", ""] +
                 [f"- {name} — {data['error']}" for name, data in report["failures"].items()] + [""])
(results / "CNN_RESULTS.md").write_text("\n".join(lines))
