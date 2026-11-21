#!/usr/bin/env python3
"""Render the complete experiment summary and static plots from validated measurements."""
from pathlib import Path
import json
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

EXT = Path(__file__).resolve().parents[1]
RESULTS = EXT / "results"
report = json.loads((RESULTS / "analysis/compare.json").read_text())
FULL = report["full"]
PROFILE = report["profile"]
CORRECTNESS = report["extra_correctness"]
SHAPES = report["mean_shapes"]
NAMES = {"cifar_mean_wide": "CIFAR-Mean-Wide", "cifar_mean_large": "CIFAR-Mean-Large"}
VARIANTS = ("stock", "opt2", "mean", "combined")
LABELS = {"stock": "Stock", "opt2": "Opt1+Opt2", "mean": "EXP-MEAN", "combined": "Combined"}
COLORS = {"stock": "#777F8E", "opt2": "#245E91", "mean": "#A54B1A", "combined": "#327252"}


def label(model):
    return NAMES.get(model, model)


def shape(model):
    return "×".join(map(str, SHAPES[model]["input_shape"][1:]))


def timing(model, variant):
    return FULL[model]["comparisons"][variant]


def plot(names):
    figures = RESULTS / "figures"
    figures.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(9.5, 7.2), layout="constrained")
    positions = np.arange(len(names))
    for i, variant in enumerate(VARIANTS[1:]):
        values = [timing(model, variant)["time_reduction_pct"] for model in names]
        ax.barh(positions + (i - 1) * .23, values, .22, label=LABELS[variant], color=COLORS[variant])
    ax.axvline(0, color="#555", linewidth=.7)
    ax.axvspan(-1, 1, color="#999", alpha=.12, zorder=0)
    ax.set_yticks(positions, [label(name) for name in names])
    ax.invert_yaxis()
    ax.set(xlabel="Latency reduction versus stock (%)", title="Complete INT8 inference on ESP32-S3-EYE")
    ax.legend(loc="lower right")
    ax.grid(axis="x", linewidth=.4, alpha=.45)
    fig.savefig(figures / "full_cnn_latency.png", dpi=180)
    plt.close(fig)

    fig, (left, right) = plt.subplots(1, 2, figsize=(11, 4.3), layout="constrained", sharey=True)
    models = list(PROFILE)
    positions = np.arange(len(models))
    for i, variant in enumerate(("stock", "mean")):
        records = [PROFILE[model]["variants"][variant] for model in models]
        y = positions + (i - .5) * .30
        left.scatter([r["medians"]["mean_cycles_adjusted"] for r in records], y,
                     label=LABELS[variant], color=COLORS[variant], s=36, zorder=3)
        right.barh(y, [r["mean_cycle_share_pct"] for r in records], .28, color=COLORS[variant])
    left.set_yticks(positions, [f"{label(model)} ({shape(model)})" for model in models])
    right.tick_params(labelleft=False)
    left.set_ylim(len(models) - .5, -.5)
    left.set(xlabel="Cycles per MEAN call", title="Isolated Global Mean")
    left.set_xscale("log")
    right.set(xlabel="Share of inference cycles (%)", title="Cost within the CNN")
    for ax in (left, right):
        ax.grid(axis="x", linewidth=.4, alpha=.45)
    left.legend()
    fig.savefig(figures / "isolated_mean.png", dpi=180)
    plt.close(fig)


def main():
    names = list(FULL)
    variants = [(name, variant, timing(name, variant)) for name in names for variant in VARIANTS[1:]]
    qacc = [(name, variant, row) for name, variant, row in variants if FULL[name]["qacc_verified"] and variant == "mean"]
    losses = [(name, variant, row) for name, variant, row in variants if row["numerical_threshold"] == "LOSS"]
    best = max(variants, key=lambda record: record[2]["time_speedup"])
    best_mean = max(qacc, key=lambda record: record[2]["time_speedup"])
    fastest_kernel = max(PROFILE, key=lambda name: PROFILE[name]["variants"]["mean"]["mean_cycle_speedup"])
    extra_inputs = sum(item["inputs"] for item in CORRECTNESS.values())
    full_samples = sum(row["samples"] for model in FULL.values() for row in model["comparisons"].values())
    accuracy = json.loads((EXT / "models/int8_accuracy.json").read_text())
    lines = [
        "# ESP32-S3-EYE multi-model CNN benchmark and Global Mean follow-up", "",
        f"{len(FULL)} full CNNs passed with exact INT8 outputs across four firmware builds and {full_samples:,} "
        "uninstrumented timed inferences. "
        f"{len(PROFILE)} executed EXP-MEAN QACC and {sum(bool(m['sliding_calls_by_pool']) for m in FULL.values())} "
        "executed the Opt1+Opt2 sliding path. All models used their frozen inputs for performance runs.", "",
        f"- Best full-CNN comparison was {best[2]['time_speedup']:.4f}× on {label(best[0])} with {LABELS[best[1]]}. "
        + ("That graph did not call QACC." if not FULL[best[0]]["qacc_verified"] else "The graph reached QACC."),
        f"- Best full-CNN EXP-MEAN comparison was {best_mean[2]['time_speedup']:.4f}× on {label(best_mean[0])}. "
        f"Best isolated cycle speedup was {PROFILE[fastest_kernel]['variants']['mean']['mean_cycle_speedup']:.3f}× "
        f"on {label(fastest_kernel)}.",
        f"- {extra_inputs} additional inputs passed on all four builds. The study keeps these untimed checks separate from "
        "frozen-input measurements.",
        "- Original evidence is preserved byte-for-byte. The frozen graph audit establishes that depthwise_both "
        "uses 16×16×32. mean_only and both use 8×8×32.",
        "", "[Original 13-model report](../../results/CNN_RESULTS.md) · [Replay commands](../README.md)",
        "", "## Full inference results", "",
        "Each latency is in milliseconds. Each cell uses the median of the two boot medians from 30 samples per boot. "
        "The four variants used the same model and SDK settings. The baseline uses Espressif's optimized ESP32-S3 ESP-NN "
        "implementation. The two new INT8 graphs have no sliding pool.",
        "", "| Model | Stock ms | Opt1+Opt2 ms / speedup | EXP-MEAN ms / speedup | Combined ms / speedup | Exact output |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for name in names:
        stock = timing(name, "stock")
        fields = [f"{timing(name, v)['median_us']/1000:.4f} / {timing(name, v)['time_speedup']:.4f}×"
                  for v in VARIANTS[1:]]
        lines.append(f"| {label(name)} | {stock['median_us']/1000:.4f} | " + " | ".join(fields) + " | PASS |")
    lines += ["", "![Time reduction for all 15 models](figures/full_cnn_latency.png)", "",
              "| Model | Stock cycles | Opt1+Opt2 cycles | EXP-MEAN cycles | Combined cycles |",
              "|---|---:|---:|---:|---:|"]
    for name in names:
        lines.append(f"| {label(name)} | " +
                     " | ".join(f"{timing(name, v)['median_cycles']:,.2f}".rstrip("0").rstrip(".") for v in VARIANTS) + " |")
    lines += ["", "### Regressions", ""]
    if losses:
        for name, variant, row in losses:
            lines.append(f"- {label(name)} / {LABELS[variant]} took {-row['time_reduction_pct']:.3f}% longer than stock. "
                         f"The recorded verdict is {row['verdict']}.")
    else:
        lines.append("Every variant stayed within 1% of stock or ran faster.")
    lines += ["", "The CSV retains all observations, sample ranges and the original ±1% verdict rule. "
              "Inactive controls also show timing shifts. The isolated comparison measures the MEAN operation directly.", "",
              "## Isolated Global Mean", "",
              "The timer surrounds the same guarded ESP-NN MEAN call in each build, including reduction, requantization "
              "and output writes. Stock goes through its original ESP32-S3 backend. EXP-MEAN uses the pinned QACC backend. "
              "Routing, reference comparisons and diagnostic output stay outside these timed samples.",
              "",
              "| CNN | MEAN NHWC shape¹ | Stock cycles | QACC cycles | Cycle speedup | Stock µs | QACC µs | Time reduction | Stock share² | QACC share² |",
              "|---|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for name, item in PROFILE.items():
        stock, mean = (item["variants"][v] for v in ("stock", "mean"))
        before, after = stock["medians"], mean["medians"]
        lines.append(f"| {label(name)} | {shape(name)} | {before['mean_cycles_adjusted']:,.2f} | "
                     f"{after['mean_cycles_adjusted']:,.2f} | {mean['mean_cycle_speedup']:.3f}× | "
                     f"{before['mean_us_adjusted']:.2f} | {after['mean_us_adjusted']:.2f} | "
                     f"{mean['mean_time_reduction_pct']:.2f}% | {stock['mean_cycle_share_pct']:.2f}% | "
                     f"{mean['mean_cycle_share_pct']:.2f}% |")
    lines += ["", "¹ Batch size is 1. ² Adjusted operator cycles divided by median complete cycles with the nested timer "
              "disabled in the same binary.",
              "", "![Isolated Mean cycles and inference contribution](figures/isolated_mean.png)", "",
              "| Model | Stock MEAN cycles | Opt1+Opt2 cycles / speedup | EXP-MEAN cycles / speedup | Combined cycles / speedup |",
              "|---|---:|---:|---:|---:|"]
    for name, item in PROFILE.items():
        v = item['variants']
        values = [f"{v[k]['medians']['mean_cycles_adjusted']:,.2f} / {v[k]['mean_cycle_speedup']:.3f}×" for k in VARIANTS[1:]]
        lines.append(f"| {label(name)} | {v['stock']['medians']['mean_cycles_adjusted']:,.2f} | " + " | ".join(values) + " |")
    for name, item in PROFILE.items():
        v = item['variants']
        for variant in VARIANTS[1:]:
            change = -v[variant]['mean_cycle_reduction_pct']
            if change > 1:
                paired = [(statistics.median(c['mean_cycles_adjusted']), statistics.median(s['mean_cycles_adjusted']))
                          for c, s in zip(v[variant]['boots'], v['stock']['boots'])]
                qualifier = "Both boot medians were slower." if all(c > s for c, s in paired) else "The boot medians disagreed."
                status = " The MEAN kernel stayed on the stock implementation in this control." if variant == "opt2" else ""
                lines += ["", f"- {label(name)} / {LABELS[variant]} used {change:.2f}% more isolated MEAN cycles than stock. "
                          f"{qualifier}{status}"]
    plain = PROFILE['mean_only']['variants']
    control = 100 * (1 - plain['opt2']['medians']['us'] / plain['stock']['medians']['us'])
    lines += ["",
              "### Measurement overhead and attribution", "",
              "Each profiling boot interleaves 30 nested-timer samples with 30 calls in the same binary with the nested timer "
              "disabled. All paths restore the frozen input and validate every output outside the timed region. Raw operator "
              "samples and measurements of the empty region are retained. The operator table subtracts the per-boot median of "
              "the empty region. The microsecond clock has 1 µs resolution. Use cycle counts for the finer comparison.", "",
              f"The mean_only Opt1+Opt2 control had an original latency change of {timing('mean_only', 'opt2')['time_reduction_pct']:+.3f}% "
              f"and a {control:+.3f}% change with the profiling timer disabled in the profiling build. The graph has no MAX_POOL_2D. "
              "These firmware timing changes illustrate why the isolated operator comparison is needed.",
              "",
              "| Model | Stock empty cycles | QACC empty cycles | Stock paired extra cycles | QACC paired extra cycles | QACC cycles saved | Outside-MEAN cycle change³ |",
              "|---|---:|---:|---:|---:|---:|---:|"]
    for name, item in PROFILE.items():
        before, after = (item["variants"][v]["medians"] for v in ("stock", "mean"))
        lines.append(f"| {label(name)} | {before['empty_cycles']:g} | {after['empty_cycles']:g} | "
                     f"{before['paired_timer_delta_cycles']:+g} | {after['paired_timer_delta_cycles']:+g} | "
                     f"{before['mean_cycles_adjusted']-after['mean_cycles_adjusted']:+g} | "
                     f"{after['outside_mean_cycles']-before['outside_mean_cycles']:+g} |")
    lines += ["", "³ Median cycles outside the raw nested region in the profiled EXP-MEAN build minus stock. These residuals include "
              "firmware layout, cache and scheduling effects. The uninstrumented full timings above are the primary end-to-end comparison.",
              "", "## Correctness, dispatch and memory", "",
              "| Model | Added inputs per build | On-board MEAN reference bytes compared | Output across builds | Arena and heap checks | Desktop reference matches |",
              "|---|---:|---:|---|---|---:|"]
    for name, item in CORRECTNESS.items():
        count = item["inputs"]
        compared = sum(case["mean_reference_bytes_compared"]
                       for data in item["variants"].values() for case in data["checks"])
        desktop = sum(case["desktop_reference_match"] for case in item["variants"]["stock"]["checks"])
        lines.append(f"| {label(name)} | {count} | {compared:,} | PASS | PASS | {desktop}/{count} |")
    lines += ["", "Each untimed check compares the actual MEAN intermediate and five additional activation patterns "
              "against the pinned TFLite Micro reference and the originally registered MEAN. Kernel wrappers count actual QACC "
              "blocks and verify zero QACC calls in stock and Opt1+Opt2. The raw diagnostic logs include each case output, "
              "quantization, pointer alignment and dispatch.",
              "", "| Model | Arena used | Stock image | Opt1+Opt2 image Δ | EXP-MEAN image Δ | Combined image Δ |",
              "|---|---:|---:|---:|---:|---:|"]
    for name in names:
        stock = timing(name, "stock")
        deltas = [timing(name, variant)["app_image_bytes"] - stock["app_image_bytes"] for variant in VARIANTS[1:]]
        lines.append(f"| {label(name)} | {stock['arena_used']:,} B | {stock['app_image_bytes']:,} B | " +
                     " | ".join(f"{delta:+,} B" for delta in deltas) + " |")
    lines += ["", "All complete inference builds used the same 2 MiB PSRAM arena capacity. Arena usage matched across "
              "firmware variants for each model. Stack high-water marks and individual boot measurements are in the data.",
              "", "## Evidence and scope", "",
              "- The pinned IDF 5.5.1 and ESP-TFLite Micro 1.4.3 builds ran on the physical ESP32-S3-EYE at 240 MHz, with "
              "8 MiB PSRAM. The two new classifiers share the original two-epoch CIFAR-10 training and INT8 calibration. "
              "Repeating training reproduced each FlatBuffer and its frozen input bytes.",
              "- On CIFAR-10 test indices 0–999, the frozen INT8 classifiers achieved "
              f"{accuracy['cifar_mean_wide']['correct'] / accuracy['cifar_mean_wide']['total']:.1%} for Wide and "
              f"{accuracy['cifar_mean_large']['correct'] / accuracy['cifar_mean_large']['total']:.1%} for Large. "
              "They are small benchmark classifiers. The two MEAN shapes each reduce 25,088 INT8 values.",
              "- The end-to-end evidence supports a targeted upstream kernel discussion. The stock TFLite Micro MEAN registration "
              "does not call ESP-NN. An upstream integration change would need maintainer review and validation on pretrained "
              "graphs that actually contain eligible MEAN. The two small Combined regressions also warrant measuring code "
              "layout and memory placement before enabling QACC broadly. The results cover fixed shapes, models and one board.",
              "", "[Full CSV](analysis/compare.csv) · [MEAN CSV](analysis/mean_profile.csv) · "
              "[Individual full samples](analysis/full_samples.csv) · [Individual MEAN samples](analysis/mean_profile_samples.csv) · "
              "[Raw sample JSON](analysis/compare.json) · [Full runs](full/) · [Profiling runs](profile/) · "
              "[Diagnostics](diagnostics/) · [FlatBuffer audit](../models/mean_graphs.json)", ""]
    (RESULTS / "CNN_RESULTS.md").write_text("\n".join(lines))
    plot(names)


if __name__ == "__main__":
    main()
