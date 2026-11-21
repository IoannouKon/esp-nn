#!/usr/bin/env python3
"""Compare the separate on-board ESP-TFLM reference check with saved stock and desktop logits."""
import json
from pathlib import Path
import re

results = Path(__file__).resolve().parents[1] / "results"
serial = results / "logs" / "suite_mobiles" / "tflm-reference-diagnostic.log"
raw = serial.read_text(errors="replace")
assert "mode=stock_tflm_reference" in raw and "CNN_SUITE_DONE" in raw
assert "Guru Meditation" not in raw
models = json.loads((results / "manifest.json").read_text())
measurements = json.loads((results / "comparison.json").read_text())["models"]
output = {}

def signed(hex_string):
    return [b if b < 128 else b - 256 for b in bytes.fromhex(hex_string)]

def differences(a, b):
    assert len(a) == len(b)
    deltas = [abs(x - y) for x, y in zip(a, b)]
    return {"mismatched_elements": sum(v != 0 for v in deltas), "max_abs_difference": max(deltas)}

pattern = r"^CNN_MODEL_BEGIN name=(\w+)\s+CNN_START .*?\n\s*CNN_REFERENCE_OUTPUT bytes=(\d+) hex=([a-f0-9]+)"
for name, length, hex_str in re.findall(pattern, raw, flags=re.M | re.S):
    values = signed(hex_str)
    assert len(values) == int(length)
    stock_values = signed(measurements[name]["firmwares"]["stock"]["runs"][0]["output_hex"])
    desktop_values = signed(models[name]["host_tflite"]["outputs_hex"][0])
    desktop_ref_values = signed(models[name]["host_reference"]["outputs_hex"][0])
    output[name] = {"reference_board_output_hex": hex_str,
                    "stock_optimized_board_vs_board_reference": differences(stock_values, values),
                    "board_reference_vs_desktop_default": differences(values, desktop_values),
                    "board_reference_vs_desktop_reference": differences(values, desktop_ref_values),
                    "saturated_elements_stock": sum(v in (-128, 127) for v in stock_values),
                    "saturated_elements_board_reference": sum(v in (-128, 127) for v in values)}
assert set(output) == {"mobilenet_v2", "mobilenet_v3_small"}, list(output)
(results / "diagnostics" / "stock_tflm_reference_results.json").write_text(json.dumps(output, indent=2) + "\n")
for model, outcome in output.items():
    print(model, {key: value for key, value in outcome.items() if not key.endswith("_hex")})
