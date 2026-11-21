#!/usr/bin/env python3
"""Enable the same experimental MEAN adapter in all four already staged apps."""
from pathlib import Path
import shutil
import sys

app = Path(sys.argv[1]) / "main"
src = Path(__file__).resolve().parent
for name in ("mean_bridge.h", "mean_bridge.cc"):
    shutil.copyfile(src / name, app / name)
p = app / "CMakeLists.txt"
s = p.read_text().replace("set(sources main.cc)", "set(sources main.cc mean_bridge.cc)")
s = s.replace("PRIV_REQUIRES esp_timer", "PRIV_REQUIRES esp-nn esp_timer")
s += '\nif(CNN_MEAN_STRESS_ONLY)\n    target_compile_definitions(${COMPONENT_LIB} PRIVATE CNN_MEAN_STRESS_ONLY=1)\nendif()\n'
p.write_text(s)
p = app / "main.cc"
s = p.read_text().replace('#include "sdkconfig.h"', '#include "sdkconfig.h"\n#include "mean_bridge.h"')
s = s.replace('resolver.AddMean()', 'resolver.AddMean(RegisterEspNnGlobalMean())')
s = s.replace('mean=builtin_tflm_reference_not_esp_nn', 'mean=guarded_esp_nn_bridge')
at = '#ifdef CNN_DISPATCH_PROBE\n    ProbeReset();'
s = s.replace(at, '#ifdef CNN_MEAN_STRESS_ONLY\n    check(ValidateEspNnGlobalMean(), "MEAN reference stress");\n    std::puts("CNN_PROBE_DONE");\n    return;\n#endif\n' + at)
p.write_text(s)
