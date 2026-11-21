#!/usr/bin/env python3
"""Check that all three experiments use byte-identical benchmark sources."""
import argparse
import json
from pathlib import Path

def check(work_root:Path):
    results=work_root/'results'
    all_runs={k:json.loads((results/f'{k}-install.json').read_text())
              for k in ('stock','exp_mean','opt2')}
    reference=all_runs['stock']
    for name,value in all_runs.items():
        if value['benchmark_files']!=reference['benchmark_files']:
            raise RuntimeError(f'{name}: benchmark app files differ from baseline')
        if value['untouched_harness_sha256']!=reference['untouched_harness_sha256']:
            raise RuntimeError(f'{name}: vendor benchmark harness differs from baseline')
        if value['manifest_sha256']!=reference['manifest_sha256']:
            raise RuntimeError(f'{name}: shape manifest differs from baseline')
    print('PASS: all three experiment app sources, vendor harness, and shape manifest match exactly')
if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--workspace',required=True,type=Path)
    a=ap.parse_args()
    check(a.workspace)
