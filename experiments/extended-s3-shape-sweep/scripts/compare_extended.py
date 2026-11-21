#!/usr/bin/env python3
"""Strict stock vs EXP-MEAN vs Opt2 benchmark result evaluator.

No fabricated data: requires full run logs, exact shape/memory matches, zero
failures/skips, both variants and identical run configs.
"""
import argparse
import csv
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
ESC=re.compile(r'\x1b\[[0-9;]*[ -/]*[@-~]')
START=re.compile(r'BENCH_START\s+target=(\S+)\s+idf=(\S+)\s+cpu_mhz=(\d+)\s+psram=(\d+)\s+iters=(\d+)\s+seed=(\S+)')
CASE=re.compile(r'BENCH op=(mean|max_pool) variant=esp_nn mem=(int|ext) ansi=(\d+) opt=(\d+) ratio=\S+ result=(\S+) shape="([^"]+)"')
SKIP=re.compile(r'BENCH op=(mean|max_pool)\s+.*result=skip')
DONE=re.compile(r'BENCH_DONE\s+cases=(\d+)\s+failures=(\d+)\s+skipped=(\d+)')
META=re.compile(r'EXTBENCH_VERSION=1\s+MEAN_CASES=(\d+)\s+POOL_CASES=(\d+)')

class ValidationError(ValueError):pass

def require(ok,msg):
    if not ok:raise ValidationError(msg)

def expected():
    manifest=json.loads((ROOT/'SHAPES.json').read_text())
    rows={}
    for op in ('mean','max_pool'):
        for x in manifest[op]:
            key=(op,x['shape'],x['mem'])
            require(key not in rows,f'Duplicate manifest shape: {key}')
            rows[key]=x
    return rows

def parse(path,refs):
    path=Path(path)
    require(path.is_file(),f'Cannot read: {path}')
    contents=ESC.sub('',path.read_text(errors='replace'))
    starts=START.findall(contents)
    dones=DONE.findall(contents)
    metas=META.findall(contents)
    require(len(starts)==1,f'{path}: expected one BENCH_START, found {len(starts)}')
    require(len(dones)==1,f'{path}: expected one BENCH_DONE, found {len(dones)}')
    require(len(metas)==1,f'{path}: expected one EXTBENCH_VERSION, found {len(metas)}')
    cfg=starts[0]
    require(cfg[0]=='esp32s3' and cfg[2]=='240',f'{path}: unexpected target/CPU: {cfg}')
    require(cfg[3]=='1',f'{path}: PSRAM not detected')
    require(cfg[4]=='9' and cfg[5].lower()=='0xc0ffee42',f'{path}: unexpected seed/iterations')
    require(tuple(map(int,metas[0]))==(42,48),f'{path}: wrong extended shape manifest')
    require(tuple(map(int,dones[0]))==(len(refs),0,0),f'{path}: cases/failures/skips: {dones[0]}')
    require(not SKIP.search(contents),f'{path}: has skipped case')
    got={}
    for op,mem,ansi,opt,result,shape in CASE.findall(contents):
        k=(op,shape,mem)
        require(k in refs, f'{path}: unexpected shape or actual memory: {k}')
        require(k not in got, f'{path}: duplicate case: {k}')
        require(result=='ok',f'{path}: incorrect result {result} for {k}')
        require(int(opt)>0,f'{path}: zero cycles for {k}')
        got[k]={'opt':int(opt),'ansi':int(ansi)}
    missing=set(refs)-set(got)
    require(not missing,f'{path}: missing {len(missing)} cases e.g. {list(missing)[:3]}')
    return {'file':str(path),'cfg':cfg,'rows':got}

def geometric(xs):
    import math
    return math.exp(sum(math.log(x) for x in xs)/len(xs)) if xs else 0.

def compare(stock_paths,mean_paths,opt2_paths,out):
    refs=expected()
    require(len(stock_paths)>=2 and len(mean_paths)>=2 and len(opt2_paths)>=2,
            'Need >=2 complete boots per firmware')
    runs={g:[parse(p,refs) for p in paths] for g,paths in
          [('stock',stock_paths),('exp_mean',mean_paths),('opt2',opt2_paths)]}
    baseline_cfg=runs['stock'][0]['cfg']
    for name,group in runs.items():
        for a in group:require(a['cfg']==baseline_cfg,f'{a["file"]}: run config differs from stock')
    rows=[]
    for k in sorted(refs):
        op,shape,mem=k
        row={'op':op,'shape':shape,'mem':mem,'eligible':refs[k]['opt_eligible']}
        for name in ('stock','exp_mean','opt2'):
            vals=[r['rows'][k]['opt'] for r in runs[name]]
            row[name+'_cycles']=vals
            row[name+'_median']=statistics.median(vals)
            row[name+'_range']=[min(vals),max(vals)]
        row['mean_speedup']=row['stock_median']/row['exp_mean_median']
        row['opt2_speedup']=row['stock_median']/row['opt2_median']
        row['mean_reduction_pct']=100*(1-row['exp_mean_median']/row['stock_median'])
        row['opt2_reduction_pct']=100*(1-row['opt2_median']/row['stock_median'])
        row['mean_verdict']=classification(row['mean_speedup'])
        row['opt2_verdict']=classification(row['opt2_speedup'])
        rows.append(row)
    groups={}
    for target,op in [('exp_mean','mean'),('opt2','max_pool')]:
        key='mean_speedup' if target=='exp_mean' else 'opt2_speedup'
        for eligible in (True,False):
            for mem in ('int','ext'):
                subset=[r for r in rows if r['op']==op and r['eligible']==eligible and r['mem']==mem]
                if not subset:continue
                groups[f'{target}|eligible={eligible}|mem={mem}']={
                    'count':len(subset),'geomean_speedup':geometric([r[key] for r in subset]),
                    'wins':sum(classification(r[key])=='WIN' for r in subset),
                    'losses':sum(classification(r[key])=='LOSS' for r in subset),
                    'neutral':sum(classification(r[key])=='NEUTRAL' for r in subset),
                    'worst_speedup':min(r[key] for r in subset),
                    'best_speedup':max(r[key] for r in subset),
                }
    result={'metadata':{'target':'esp32s3','esp_nn_stock':'ace42ac7721119cd543fc40ffe719e601fa8f20f',
                       'runs_per_build':{k:len(r) for k,r in runs.items()},
                       'configs':list(baseline_cfg),'model_level':'NOT MEASURED'},
            'groups':groups,'rows':rows,'logs':{k:[r['file'] for r in v] for k,v in runs.items()}}
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    (out/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    fields=['op','shape','mem','eligible','stock_median','exp_mean_median','opt2_median',
            'mean_speedup','opt2_speedup','mean_reduction_pct','opt2_reduction_pct',
            'mean_verdict','opt2_verdict','stock_range','exp_mean_range','opt2_range']
    with (out/'comparison.csv').open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
    content=[
        '# Extended ESP32-S3-EYE benchmark — measured results',
        '', '> All CPU-cycle values below are populated strictly from hardware serial logs.',
        '> This is an **extended** experimental sweep using the original ESP-NN benchmark harness,',
        '> not the vendor’s official shape matrix and **not** full-CNN inference.',
        '', '## Verification',
        f'- Complete boots: '+', '.join(f'{g}={len(r)}' for g,r in runs.items()),
        '- All expected 90 cases were present and correctness/guard checks passed on every boot.',
        '- Same target, CPU frequency, PSRAM detection, random seed, and benchmark iterations.',
        '- Individual runs use the vendor harness minimum of the eight post-warmup measurements.',
        '', '## Group summaries',
        '| Kernel branch | Opt path eligible | Memory | Cases | Geomean speedup | Wins (>1%) | Losses (>1%) | Neutral | Worst speedup |',
        '|---|---|---|---:|---:|---:|---:|---:|---:|'
    ]
    for key,d in groups.items():
        name,e,mem=key.split('|')
        content.append(f'| {name} | {e[9:]} | {mem[4:]} | {d["count"]} | {d["geomean_speedup"]:.3f}× | {d["wins"]} | {d["losses"]} | {d["neutral"]} | {d["worst_speedup"]:.3f}× |')
    content+=['','## Complete table — all cases','',
        '| Operation | Shape | Mem | Eligible | Stock cycles | EXP-MEAN cycles | Mean speedup | Opt2 cycles | Opt2 speedup |',
        '|---|---|---|:---:|---:|---:|---:|---:|---:|']
    for r in rows:
        content.append(f'| {r["op"]} | {r["shape"]} | {r["mem"]} | {"Y" if r["eligible"] else "N"} | {r["stock_median"]:g} | {r["exp_mean_median"]:g} | {r["mean_speedup"]:.3f}× | {r["opt2_median"]:g} | {r["opt2_speedup"]:.3f}× |')
    content+=['','## Interpretation rules','',
      '- Focus on **EXP-MEAN vs stock** for mean and **Opt2 vs stock** for max pooling.',
      '- Other-operation columns are controls, not proof of the optimized algorithm.',
      '- Mean eligibility requires `channels % 16 == 0` and `H×W ≤ 4095`; otherwise scalar fallback.',
      '- Opt2 eligibility requires aligned, disjoint buffers, channel multiple of 16, 3×3/5×5 stride-1 SAME, and input dimensions ≥ filter.',
      '- A reported neutral fallback change is **not** an algorithm win.',
      '- Show losing shapes, including if they are eligible. Keep all 90 results.',
      '- Real-time/cold-cache CNN improvements are unmeasured.',
      '']
    (out/'RESULTS.md').write_text('\n'.join(content))
    print(f'Validated {len(refs)} cases across {sum(len(r) for r in runs.values())} boots; wrote {out}/RESULTS.md')
    return result

def classification(speedup):
    if speedup > 1.01:return 'WIN'
    if speedup < 1/1.01:return 'LOSS'
    return 'NEUTRAL'

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stock',nargs='+',type=Path,required=True)
    p.add_argument('--mean',nargs='+',type=Path,required=True)
    p.add_argument('--opt2',nargs='+',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    try:compare(a.stock,a.mean,a.opt2,a.out)
    except ValidationError as e:p.error(str(e))
