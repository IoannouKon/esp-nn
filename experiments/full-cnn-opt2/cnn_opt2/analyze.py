"""Validate diagnostic and timing serial logs and summarize the board results."""
import json
import re
from pathlib import Path
from statistics import median
import sys

logs = Path(sys.argv[1])
diagnostic = (logs / "probe.log").read_text()
pattern = (
    r"CNN_POOL input=(\S+) output=(\S+) shape=(\d+)x(\d+)x(\d+) "
    r"out=(\d+)x(\d+) filter=(\d+)x(\d+) stride=1x1 pad=(\d+)x(\d+) sliding_rows=(\d+)"
)
layers = re.findall(pattern, diagnostic)
assert diagnostic.count("CNN_DONE") == 1 and len(layers) == 2
for layer, expected in zip(layers, [(14, 14, 16, 3), (7, 7, 32, 5)]):
    input_addr, output_addr = (int(value, 16) for value in layer[:2])
    width, height, channels, out_w, out_h, filter_w, filter_h, pad_w, pad_h, rows = map(int, layer[2:])
    assert (width, height, channels, filter_w) == expected
    assert (out_w, out_h, filter_h) == (width, height, filter_w)
    assert pad_w == pad_h == filter_w // 2
    assert (input_addr | output_addr) & 15 == 0
    assert abs(input_addr - output_addr) >= width * height * channels
    assert rows == height * (channels // 16)

measurements = {}
arena_settings = set()
for build in ("stock", "opt2"):
    log = (logs / f"{build}.log").read_text()
    starts = re.findall(
        r"CNN_START cpu_mhz=240 arena=psram arena_address=(\S+) arena_bytes=(\d+) arena_used=(\d+)",
        log,
    )
    assert len(starts) == log.count("CNN_DONE") == 2
    assert "CNN_POOL " not in log and "CNN_ERROR" not in log
    arena_settings.update(starts)
    rows = re.findall(r"CNN_RUN (\d+) us=(\d+) output=([-\d,]+)", log)
    assert [int(row[0]) for row in rows] == list(range(1, 21)) * 2
    times = [int(row[1]) for row in rows]
    values = [list(map(int, row[2].split(","))) for row in rows]
    assert all(len(output) == 10 and all(-128 <= value <= 127 for value in output) for output in values)
    measurements[build] = {
        "times_us": [times[:20], times[20:]],
        "median_us": median(times),
        "boot_medians_us": [median(times[:20]), median(times[20:])],
        "min_us": min(times),
        "max_us": max(times),
        "outputs": values,
    }
stock, opt2 = (measurements[name] for name in ("stock", "opt2"))
assert len(arena_settings) == 1, arena_settings
differences = [
    abs(a - b)
    for stock_output, opt2_output in zip(stock["outputs"], opt2["outputs"])
    for a, b in zip(stock_output, opt2_output)
]
all_outputs = stock["outputs"] + opt2["outputs"]
mismatches = sum(diff != 0 for diff in differences)
stable_outputs = all(output == all_outputs[0] for output in all_outputs)
time_reduction = 100 * (stock["median_us"] - opt2["median_us"]) / stock["median_us"]
if mismatches or not stable_outputs:
    verdict = "FAIL (output mismatch or nondeterminism)"
elif opt2["max_us"] < stock["min_us"]:
    verdict = "WIN"
elif stock["max_us"] < opt2["min_us"]:
    verdict = "LOSE"
else:
    verdict = "NO CLEAR CHANGE (observed timing ranges overlap)"

print(json.dumps({
    "arena": list(arena_settings)[0],
    "stock": stock,
    "opt2": opt2,
    "compared_int8_elements": len(differences),
    "output_mismatches": mismatches,
    "max_abs_output_difference": max(differences),
    "stable_outputs": stable_outputs,
    "speedup": stock["median_us"] / opt2["median_us"],
    "time_reduction_pct": time_reduction,
    "verdict": verdict,
}, indent=2))
