"""Verify two physical boots of the historical MNIST app and report paired outputs."""
from hashlib import sha256
import json
from pathlib import Path
import re
from statistics import median

root = Path(__file__).resolve().parent
results = root / "results"
variants = ("stock", "opt2", "exp-mean")
boot = re.compile(r"^CNN_START (.+?)\n(.*?)^CNN_DONE\s*$", re.M | re.S)
sample = re.compile(r"^CNN_RUN (\d+) us=(\d+) output=([-\d,]+)\s*$", re.M)
ansi = re.compile(r"\x1b\[[0-9;]*[a-zA-Z]")
expected = [-32, -4, 44, 14, -24, -25, -103, 98, -24, 30]
configuration = (results / "original.sdkconfig").read_bytes()
reports = {}
arena_settings = set()

def checked_boots(label, count):
    raw = ansi.sub("", (results / f"{label}.log").read_text())
    assert not any(x in raw for x in ("CNN_ERROR", "Guru Meditation", "Task watchdog got triggered", "abort()"))
    assert raw.count("cpu freq: 240000000 Hz") == count
    assert raw.count("Found 8MB PSRAM device") == count
    digests = re.findall(r"ELF file SHA256:\s+([0-9a-f]+)", raw)
    recorded = (results / f"{label}.elf.sha256").read_text().split()[0]
    assert len(digests) == count and all(recorded.startswith(x) for x in digests)
    assert "Hash of data verified." in raw
    boots = boot.findall(raw)
    assert len(boots) == count, label
    for setup, _ in boots:
        assert "cpu_mhz=240 arena=psram " in setup and "arena_bytes=98304 arena_used=28396" in setup
        address = int(re.search(r"arena_address=(0x[0-9a-f]+)", setup)[1], 16)
        assert address % 16 == 0
        arena_settings.add(setup)
    return boots

graphs = json.loads((results / "graph.json").read_text())
assert [[n["name"] for n in g] for g in graphs] == [[
    "CONV_2D", "MAX_POOL_2D", "CONV_2D", "MAX_POOL_2D", "RESHAPE", "FULLY_CONNECTED"]]
for label in variants:
    assert (results / f"{label}.sdkconfig").read_bytes() == configuration
    lock = (results / f"{label}.dependencies.lock").read_text()
    sources = re.findall(r"^    source:\n      path: (.+)\n      type: local$", lock, re.M)
    assert [Path(source).name for source in sources] == ["espressif__esp-nn", "esp-tflite-micro"]
    assert len({Path(source).parent for source in sources}) == 1
    syms = (results / f"{label}.symbols.txt").read_text()
    assert "esp_nn_max_pool_s8_esp32s3" in syms and "__wrap_" not in syms
    assert ("esp_nn_max_pool_s8_esp32s3_sliding_row_asm" in syms) == (label == "opt2")
    assert "esp_nn_mean" not in syms and "Register_MEAN" not in syms
    entries = []
    for _, body in checked_boots(label, 2):
        rows = sample.findall(body)
        assert [int(i) for i, _, _ in rows] == list(range(1, 21))
        times = [int(t) for _, t, _ in rows]
        outputs = [[int(x) for x in output.split(",")] for _, _, output in rows]
        assert all(output == expected for output in outputs)
        entries.append(dict(times_us=times, outputs=outputs, median_us=median(times),
                            min_us=min(times), max_us=max(times)))
    all_times = [time for entry in entries for time in entry["times_us"]]
    reports[label] = dict(boots=entries, median_us=median(all_times), min_us=min(all_times),
                          max_us=max(all_times),
                          commit=(results / f"{label}.esp-nn.txt").read_text().strip())

[(_, diagnostic)] = checked_boots("opt2-probe", 1)
rows = re.findall(r"^CNN_POOL .*?sliding_rows=(\d+)\s*$", diagnostic, re.M)
assert [int(x) for x in rows] == [14, 14]
assert len(arena_settings) == 1, arena_settings

stock = reports["stock"]["median_us"]
for r in reports.values():
    r["speedup"] = stock / r["median_us"]
    r["reduction_pct"] = 100 * (stock - r["median_us"]) / stock
summary = {"firmwares": reports, "tflm": "df8722334a80ceabc609c1e72968f417cd9437f1",
           "sdkconfig_sha256": sha256(configuration).hexdigest(), "arena": arena_settings.pop(),
           "output_reference": expected, "total_inferences": 120, "mismatches": 0,
           "opt2_sliding_calls": list(map(int, rows)), "exp_mean_executed": False}
(results / "comparison.json").write_text(json.dumps(summary, indent=2) + "\n")
for label, r in reports.items():
    print(label, r["median_us"], r["speedup"], r["reduction_pct"], r["min_us"], r["max_us"],
          [b["median_us"] for b in r["boots"]])
