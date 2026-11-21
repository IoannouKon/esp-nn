#!/usr/bin/env python3
"""Mock-log self-test for parser only; not hardware benchmark evidence."""
from pathlib import Path
import subprocess, tempfile, sys
src=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as td:
    root=Path(td)/'logs'/'mock';root.mkdir(parents=True)
    for v in ('stock','opt2','mean','combined'):
        for boot in (1,2):
            ms=1000 if v in ('stock','mean') else 800
            body=f'CNN_START cpu_mhz=240\nCNN_OUTPUT bytes=2 hash_fnv1a=12345abc stable=1 hex=00fe\n'
            body+=''.join(f'CNN_RUN index={i+1} us={ms+i%2}\n' for i in range(30))
            body+='CNN_DONE samples=30 median_us=800 min_us=800 max_us=801\n'
            (root/f'{v}-{boot}.log').write_text(body)
    subprocess.run([sys.executable,str(src/'scripts/compare_cnn.py'),str(Path(td)/'logs'),'--out',str(Path(td)/'analysis/comparison')],check=True,stdout=subprocess.DEVNULL)
    assert (Path(td)/'analysis/comparison.json').exists()
    (root/'mean-2.log').write_text('CNN_ERROR invoke\n')
    z=subprocess.run([sys.executable,str(src/'scripts/compare_cnn.py'),str(Path(td)/'logs'),'--out',str(Path(td)/'analysis/failed')],capture_output=True,text=True)
    assert z.returncode != 0
print('PASS mock-log parser rejects incomplete logs; no hardware measurements were performed')
