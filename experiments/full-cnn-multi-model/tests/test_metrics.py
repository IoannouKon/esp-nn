from pathlib import Path
import subprocess,sys,tempfile
ROOT=Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory() as td:
    d=Path(td)/'logs'/'example';d.mkdir(parents=True)
    for variant in ('stock','opt2','mean','combined'):
        for boot in (1,2):
            time=2000 if variant in ('stock','mean') else 1800
            cyc=480000 if variant in ('stock','mean') else 430000
            lines=['CNN_START cpu_mhz=240 arena=psram output_bytes=4']
            for i in range(30):lines.append(f'CNN_RUN index={i} us={time} cycles={cyc}')
            lines.extend(['CNN_OUTPUT bytes=4 hash_fnv1a=c3aa51b1 stable=1 hex=00010203',f'CNN_DONE samples=30 median_us={time} median_cycles={cyc}'])
            (d/f'{variant}-{boot}.log').write_text('\n'.join(lines)+'\n')
    result=subprocess.run([sys.executable,str(ROOT/'scripts/compare_cnn.py'),str(d.parent),'--out',str(Path(td)/'analysis')],capture_output=True,text=True)
    assert result.returncode==0,result.stderr+result.stdout
    assert '1.111x' in result.stdout
    f=d/'mean-2.log';s=f.read_text().replace('hex=00010203','hex=00010204');f.write_text(s)
    result=subprocess.run([sys.executable,str(ROOT/'scripts/compare_cnn.py'),str(d.parent),'--out',str(Path(td)/'analysis')],capture_output=True,text=True)
    assert result.returncode!=0,'Must detect output mismatch'
print('METRICS_HOST_SMOKE_PASS')
