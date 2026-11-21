#!/usr/bin/env python3
"""Stage the verbatim original timing app or apply a follow-up-only overlay."""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

EXT = Path(__file__).resolve().parents[1]
KIT = EXT.parent
VARIANTS = ("stock", "opt2", "mean", "combined")


def edit(path, old, new):
    text = path.read_text()
    if text.count(old) != 1:
        raise ValueError(f"Unexpected source in {path}: {old!r}")
    path.write_text(text.replace(old, new))


def stage(workspace, mode, cases):
    for variant in VARIANTS:
        app = workspace / variant / "app"
        main = app / "main"
        for filename in ("main.cc", "CMakeLists.txt", "probe.cc"):
            shutil.copyfile(KIT / "app" / "main" / filename, main / filename)
        subprocess.run([sys.executable, KIT / "integration/enable_bridge.py", app], check=True)
        if mode == "profile":
            for filename in ("mean_profile.h", "profile_invokes.inc"):
                shutil.copyfile(EXT / "firmware" / filename, main / filename)
            edit(main / "main.cc", '#include "mean_bridge.h"',
                 '#include "mean_bridge.h"\n#include "mean_profile.h"\n\nbool profile_mean = false;\nMeanMeasurement mean_measurement;')
            path = main / "main.cc"
            source = path.read_text()
            start = source.index("    std::vector<int64_t> times;")
            end = source.index('    std::printf("CNN_OUTPUT', start)
            path.write_text(source[:start] + '#include "profile_invokes.inc"\n' +
                            '    for (size_t i = 0; i < reference.size(); ++i)\n' +
                            '        checksum = (checksum ^ reference[i]) * 16777619u;\n' + source[end:])
            edit(main / "mean_bridge.cc", '#include "mean_bridge.h"',
                 '#include "mean_bridge.h"\n#include "mean_profile.h"')
            edit(main / "mean_bridge.cc", "    RunEspNn(in->data.int8, out->data.int8, data);\n    return kTfLiteOk;",
                 """    if (profile_mean) {
        const MeanTimer timer;
        RunEspNn(in->data.int8, out->data.int8, data);
        const MeanMeasurement sample = timer.Read();
        mean_measurement.calls += sample.calls;
        mean_measurement.cycles += sample.cycles;
        mean_measurement.us += sample.us;
    } else {
        RunEspNn(in->data.int8, out->data.int8, data);
    }
    return kTfLiteOk;""")
        if mode == "correctness":
            shutil.copyfile(EXT / "firmware/correctness_invokes.inc", main / "correctness_invokes.inc")
            shutil.copyfile(cases, main / "correctness_inputs.bin")
            edit(main / "CMakeLists.txt", 'EMBED_FILES "model.tflite" "input.bin"',
                 'EMBED_FILES "model.tflite" "input.bin" "correctness_inputs.bin"')
            edit(main / "main.cc", "    ProbeReset();\n    check(interpreter.Invoke() == kTfLiteOk, \"diagnostic invoke\");\n    ProbeReport();",
                 '#include "correctness_invokes.inc"')
            # Leave the measured build unchanged. Add arena boundary guards only in this mode.
            edit(main / "main.cc", """    uint8_t *arena = static_cast<uint8_t *>(heap_caps_aligned_alloc(
        16, CNN_ARENA_BYTES, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
    check(arena && esp_ptr_external_ram(arena), "psram arena");""",
                 """    uint8_t* guarded_arena = static_cast<uint8_t*>(heap_caps_aligned_alloc(
        16, CNN_ARENA_BYTES + 64, MALLOC_CAP_SPIRAM | MALLOC_CAP_8BIT));
    check(guarded_arena && esp_ptr_external_ram(guarded_arena), "psram arena");
    std::memset(guarded_arena, 0x71, 32);
    uint8_t* arena = guarded_arena + 32;
    std::memset(arena + CNN_ARENA_BYTES, 0x71, 32);""")
            edit(main / "correctness_invokes.inc", "    vTaskDelay(1);",
                 """    const auto intact = [](uint8_t byte) { return byte == 0x71; };
    check(std::all_of(guarded_arena, arena, intact) &&
          std::all_of(arena + CNN_ARENA_BYTES, arena + CNN_ARENA_BYTES + 32, intact), "arena guards");
    vTaskDelay(1);""")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("mode", choices=("full", "profile", "correctness"))
    parser.add_argument("--cases", type=Path)
    args = parser.parse_args()
    if args.mode == "correctness" and not args.cases:
        parser.error("correctness mode needs --cases")
    stage(args.workspace, args.mode, args.cases)
