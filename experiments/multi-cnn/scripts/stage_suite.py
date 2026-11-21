#!/usr/bin/env python3
"""Stage one immutable model bundle in a detached firmware workspace."""
import argparse
from pathlib import Path
import shutil
import re

parser = argparse.ArgumentParser()
parser.add_argument("dest", type=Path)
parser.add_argument("models", nargs="+")
parser.add_argument("--validation", action="store_true")
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
shutil.copytree(root / "app", args.dest, dirs_exist_ok=True,
                ignore=shutil.ignore_patterns("build*", "sdkconfig", "dependencies.lock"))
main = args.dest / "main"
if (main / "suite_models.h").exists():
    for staged in main.iterdir():
        if re.fullmatch(r"(?:model|input|validation)_\d+\.(?:tflite|bin)", staged.name):
            staged.unlink()
files = []
declarations = []
rows = []
for i, name in enumerate(args.models):
    if not re.fullmatch(r"[a-z0-9_]+", name):
        parser.error(f"Invalid model name {name}")
    names = []
    for kind, ext in (("model", "tflite"), ("input", "bin")):
        ident = f"{kind}_{i}"
        filename = f"{ident}.{ext}"
        shutil.copyfile(root / "models" / name / f"{kind}.{ext}", main / filename)
        files.append(filename)
        for end in ("start", "end"):
            symbol = f"{ident}_{end}"
            declarations.append(f'extern const uint8_t {symbol}[] asm("_binary_{ident}_{ext}_{end}");')
            names.append(symbol)
    validation = root / "models" / name / "validation.bin"
    if args.validation and validation.exists():
        ident = f"validation_{i}"
        filename = f"{ident}.bin"
        shutil.copyfile(validation, main / filename)
        files.append(filename)
        for end in ("start", "end"):
            symbol = f"{ident}_{end}"
            declarations.append(f'extern const uint8_t {symbol}[] asm("_binary_{ident}_bin_{end}");')
            names.append(symbol)
    else:
        names += ["nullptr", "nullptr"]
    rows.append(f'    {{"{name}", {", ".join(names)}}},')
(main / "suite_models.h").write_text("\n".join(declarations) +
    "\n\nconstexpr ModelBlob kModels[] = {\n" + "\n".join(rows) + "\n};\n")
(main / "suite_models.cmake").write_text("set(model_files " + " ".join(files) + ")\n")
