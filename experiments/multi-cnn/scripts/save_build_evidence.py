#!/usr/bin/env python3
"""Record build inputs, compiled sources, linked symbols and firmware sizes."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import re
import shutil
import subprocess

p = argparse.ArgumentParser()
p.add_argument("workspace", type=Path)
p.add_argument("variant")
p.add_argument("group")
p.add_argument("--build", default="build")
a = p.parse_args()
kit = Path(__file__).resolve().parents[1]
base = a.workspace.resolve() / a.variant
app = base / "app"
build = app / a.build
stem = "espnn_multi_cnn"
elf = build / f"{stem}.elf"
firmware = build / f"{stem}.bin"
dest = kit / "results" / "build" / f"{a.group}-{a.variant}-{a.build}"
dest.mkdir(parents=True, exist_ok=True)

def hash_file(f):
    return sha256(f.read_bytes()).hexdigest()

def cmd(*args, cwd=None):
    return subprocess.check_output(args, text=True, cwd=cwd)

def save(name, text):
    (dest / name).write_text(text)

for filename in ("sdkconfig", "sdkconfig.defaults", "dependencies.lock", "partitions.csv", "main/suite_models.h",
                 "main/suite_models.cmake"):
    shutil.copyfile(app / filename, dest / Path(filename).name)

compiler = "xtensa-esp32s3-elf"
save("toolchain.txt", cmd(compiler + "-gcc", "--version") + cmd("idf.py", "--version"))
symbols = cmd(compiler + "-nm", "-S", "-C", str(elf))
names = [line for line in symbols.splitlines()
         if re.search(r"esp_nn_(max_pool_s8|mean_)|RegisterEspNnGlobalMean|__wrap_|_binary_(model|input|validation)_", line)]
save("symbols.txt", "\n".join(names) + "\n")
command_list = json.loads((build / "compile_commands.json").read_text())
commands = [e for e in command_list if re.search(r"/esp-nn/src/|/main/(?:main|mean_bridge|probe)\.cc$|/kernels/(?:reduce_common|esp_nn/pooling|esp_nn/reduce)\.cc$", e["file"])]
save("compile_commands.selected.json", json.dumps(commands, indent=2) + "\n")
git = base / "esp-nn"
save("esp-nn-status.txt", cmd("git", "rev-parse", "HEAD", cwd=git) + cmd("git", "status", "--short", cwd=git))
save("esp-nn-working.diff", cmd("git", "diff", "--binary", cwd=git))
pools = [f for f in (git / "src/pooling").glob("*max_pool*s8*") if "esp32s3" in f.name]
means = list((git / "src/common").glob("*mean*"))
sizes = cmd(compiler + "-size", str(elf))
save("elf_size.txt", sizes)
boot_sel = re.findall(r'\s(\d+)\s+(\d+)\s+(\d+)\s+\d+\s+[0-9a-f]+\s', sizes)[0]
binary = firmware.read_bytes()
files = {f.name: {"bytes": f.stat().st_size, "sha256": hash_file(f)}
         for f in sorted((app / "main").iterdir())
         if f.is_file()}
# ESP-IDF embeds opaque data unchanged in flash. Check compiled bytes, not just the staged files.
hashes = {f.name: {"sha256": files[f.name]["sha256"], "embedded": f.read_bytes() in binary}
          for f in (app / "main").iterdir()
          if re.fullmatch(r"(?:model|input|validation)_\d+\.(?:tflite|bin)", f.name)
          and (a.build == "build" or not f.name.startswith("validation_"))}
if a.build == "build":
    for suffix in ("bin", "elf"):
        shutil.copyfile(build / f"{stem}.{suffix}", dest / f"{stem}.{suffix}")
config = {
    "firmware_bytes": len(binary), "firmware_sha256": hash_file(firmware), "elf_sha256": hash_file(elf),
    "text_data_bss": list(map(int, boot_sel)), "sdkconfig_sha256": hash_file(app / "sdkconfig"),
    "firmware_blobs": hashes, "app_sources": files,
    "kernel_sources": {str(f.relative_to(git)): hash_file(f) for f in sorted(pools + means)},
}
save("evidence.json", json.dumps(config, indent=2) + "\n")
if not all(v["embedded"] for v in hashes.values()):
    raise SystemExit("A frozen model or input was missing from the firmware image")
if a.build == "build" and "__wrap_esp_nn_" in symbols:
    raise SystemExit("Timed firmware unexpectedly contains a dispatch wrapper")
