#!/usr/bin/env python3
"""Compare per-model, per-version complete Invoke timings and exact outputs.
Usage: compare_cnn.py DIR containing <model>/<version>-<boot>.log
"""
import argparse,collections,csv,json,re,statistics
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('log_root');p.add_argument('--out',default='results/comparison');args=p.parse_args()
rx_run=re.compile(r'CNN_RUN index=(\d+) us=(\d+)');rx_out=re.compile(r'CNN_OUTPUT bytes=(\d+) hash_fnv1a=([0-9a-f]+) stable=(\d+) hex=([0-9a-f]*)');
results={};root=Path(args.log_root)
for f in root.glob('*/*.log'):
    model=f.parent.name; version=f.stem.rsplit('-',1)[0]
    s=f.read_bytes().decode('utf-8','replace').replace('\r','')
    times=[int(t) for _,t in rx_run.findall(s)]
    mo=rx_out.search(s)
    if not ('CNN_DONE ' in s and len(times)>=20 and mo and int(mo[3])==1 and len(mo[4])==2*int(mo[1])):
        raise SystemExit(f'INVALID or truncated log: {f}')
    k=(model,version);results.setdefault(k,[]).append({'log':str(f),'times_us':times,'median_us':statistics.median(times),'output_hex':mo[4],'output_bytes':int(mo[1])})
rows=[]
for model in sorted({m for m,v in results}):
    for v in ('stock','opt2','mean','combined'):
        runs=results.get((model,v),[])
        if len(runs)<2:raise SystemExit(f'Missing two boots: {model}/{v}')
        reference_outputs={r['output_hex'] for r in results[(model,'stock')]}
        if len(reference_outputs)!=1 or any(r['output_hex'] not in reference_outputs for r in runs):
            raise SystemExit(f'OUTPUT_MISMATCH: {model}/{v}')
        median=statistics.median(r['median_us'] for r in runs)
        stock=statistics.median(r['median_us'] for r in results[(model,'stock')])
        ratio=stock/median
        rows.append({'model':model,'version':v,'stock_us':stock,'candidate_us':median,'speedup':round(ratio,5),'reduction_pct':round(100*(1-median/stock),3),
                     'verdict':'WIN' if ratio>1.01 else ('LOSS' if ratio<1/1.01 else 'NEUTRAL'),
                     'boots':len(runs),'output_identical':True,'all_times_us':[t for r in runs for t in r['times_us']],
                     'meaning':'Built-in TFLM MEAN reference; EXP-MEAN NOT exercised unless independently proven with verified bridge.' if v in ('mean','combined') else 'Opt2 routing still requires diagnostic proof.'})
where=Path(args.out);where.parent.mkdir(parents=True,exist_ok=True)
(where.with_suffix('.json')).write_text(json.dumps({'rows':rows,'runs':{f'{k[0]}/{k[1]}':v for k,v in results.items()}},indent=2)+'\n')
with where.with_suffix('.csv').open('w',newline='') as f:
    fields=['model','version','stock_us','candidate_us','speedup','reduction_pct','verdict','boots','output_identical','meaning']
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows({k:r[k] for k in fields} for r in rows)
for r in rows:print('{model:18} {version:9} {candidate_us:9.1f} us {speedup:7.3f}x {verdict}'.format(**r))
