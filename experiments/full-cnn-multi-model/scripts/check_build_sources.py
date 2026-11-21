#!/usr/bin/env python3
"""Reject wrong ESP-NN or TFLM sources; no registry stock fallback."""
import json,sys
from pathlib import Path
if len(sys.argv)!=4:raise SystemExit('Usage: check_build_sources.py BUILD_DIR ESP_NN_DIR ESP_TFLM_DIR')
build,esp,tfm=(Path(x).resolve() for x in sys.argv[1:])
f=build/'compile_commands.json'
if not f.exists():raise SystemExit('MISSING compile_commands.json (enable CMAKE_EXPORT_COMPILE_COMMANDS or inspect build manually)')
commands=json.loads(f.read_text())
files=[Path(c['file']).resolve() for c in commands]
for root,name in ((esp,'ESP-NN'),(tfm,'ESP-TFLM')):
    relevant=[p for p in files if p.is_relative_to(root)]
    if not relevant:raise SystemExit('BAD: no '+name+' sources compiled from '+str(root))
    print('GOOD',name,root,'files',len(relevant))
for p in files:
    if any(x in ('esp-nn','espressif__esp-nn') for x in p.parts[:-1]) and 'src' in p.parts and not p.is_relative_to(esp):
        raise SystemExit('UNEXPECTED ESP-NN SOURCE: '+str(p))
print('LOCAL_COMPONENT_SOURCE_CHECK_PASS')
