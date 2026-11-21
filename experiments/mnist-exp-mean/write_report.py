import json
from pathlib import Path

results = Path(__file__).resolve().parent / "results"
summary = json.loads((results / "comparison.json").read_text())
firmwares = summary["firmwares"]
names = {"stock": "Stock ESP-NN v1.5.0", "opt2": "Opt1 + Opt2", "exp-mean": "EXP-MEAN"}
old = {"stock": 2910, "opt2": 2660}
lines = ["# Frozen INT8 MNIST CNN – EXP-MEAN comparison", "",
         "The original full-CNN runner ran unchanged on the ESP32-S3-EYE at 240 MHz over USB Serial/JTAG "
         "on /dev/ttyACM0. Each timed build recorded 20 complete Invoke calls on each of two boots, after "
         "three warm-ups on each boot. The median uses all 40 timings per build.", "",
         "| Firmware | Median (ms) | Speedup vs stock | Time reduction | Boot medians (µs) | All samples (µs) |",
         "|---|---:|---:|---:|---|---|"]
for key, r in firmwares.items():
    boots = " / ".join(f'{b["median_us"]:g}' for b in r["boots"])
    lines.append(f'| {names[key]} | {r["median_us"]/1000:.4f} | {r["speedup"]:.4f}× | '
                 f'{r["reduction_pct"]:+.3f}% | {boots} | {r["min_us"]}–{r["max_us"]} |')
lines += ["", "## Historical comparison", "",
          "| Implementation | Previous median | Current median | Change (µs) |",
          "|---|---:|---:|---:|"]
for key, before in old.items():
    now = firmwares[key]["median_us"]
    lines.append(f"| {names[key]} | {before/1000:.3f} ms | {now/1000:.4f} ms | {now-before:+g} |")
lines += ["", "## Correctness and dispatch", "",
          "All 120 timed inferences returned the original ten INT8 logits, with zero mismatched elements. "
          "The predicted digit was 7.", "",
          "The original untimed probe logged 14 calls to the Opt2 sliding-row assembly for each of the "
          "3×3 and 5×5 max-pool layers. The timed ELFs contained no dispatch wrappers. The stock and EXP-MEAN "
          "ELFs linked the stock ESP32-S3 max-pool entry point.", "",
          "The frozen FlatBuffer contains two Conv2D layers, two MaxPool layers, Reshape and FullyConnected. "
          "The app registers only those four operator types. The EXP-MEAN timed ELF contains neither a linked "
          "TFLite Micro MEAN registration nor a linked ESP-NN global-mean or QACC function. EXP-MEAN executed zero "
          "times. Its timing is a negative control and the difference is not attributable to the mean optimization.", "",
          "## Reproduction evidence", "",
          "- ESP-TFLite Micro v1.4.3 at " + summary["tflm"] + ".",
          "- ESP-IDF v5.5.1 at fcae32885b0296b32044cb99ecbdc50d98dddb83, Xtensa GCC 14.2.0.",
          "- Single core, 240 MHz, 8 MiB octal PSRAM at 80 MHz, 64 KiB data cache and 16 KiB instruction cache.",
          "- The exact original SDK config and frozen model/input were reused. The aligned 96 KiB PSRAM arena "
          "used 28,396 bytes on every captured boot.",
          "- SDK config SHA-256 " + summary["sdkconfig_sha256"] + "."]
for key, r in firmwares.items():
    lines.append(f'- {names[key]} at {r["commit"]}. [{key} raw serial log]({key}.log)')
lines += ["", "[Complete Opt2 diagnostic log](opt2-probe.log) · [Graph operator audit](graph.json) · "
          "[Every timing and output tensor](comparison.json) · [Original SDK config](original.sdkconfig) · "
          "[Frozen model/input hashes](model-input.sha256)", ""]
(results / "MNIST_EXP_MEAN_RESULTS.md").write_text("\n".join(lines))
