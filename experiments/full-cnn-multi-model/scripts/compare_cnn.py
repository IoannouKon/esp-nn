#!/usr/bin/env python3
"""Strict cross-firmware comparison of full outputs and 30*2 cycles + time samples."""
import argparse,csv,hashlib,json,re,statistics,sys
from pathlib import Path
RUN=re.compile(r'CNN_RUN index=(\d+) us=(\d+) cycles=(\d+)')
OUTPUT=re.compile(r'CNN_OUTPUT bytes=(\d+) hash_fnv1a=([0-9a-f]+) stable=(\d+) hex=([0-9a-f]*)')
START=re.compile(r'CNN_START .*')
EXPECTED=('stock','opt2','mean','combined')

def parse(f):
    s=f.read_bytes().decode('utf-8','replace').replace('\r','')
    if 'CAPTURE_RESET_SENT' in s:
        s=s.rsplit('CAPTURE_RESET_SENT',1)[1]
    if any(x in s for x in ('CNN_ERROR','Guru Meditation','Task watchdog got triggered')):
        raise ValueError('Firmware warning or failure '+str(f))
    sdk=f.with_suffix('.sdkconfig')
    fingerprint=f.with_suffix('.elf.sha256')
    image_bytes=None
    sdkconfig_sha256=None
    if fingerprint.exists():
        elf=re.findall(r'ELF file SHA256:\s+([a-f0-9]+)',s)
        assert len(elf)==1 and fingerprint.read_text().split()[0].startswith(elf[0]), ('Wrong flashed ELF',f)
        assert 'cpu freq: 240000000 Hz' in s and 'Found 8MB PSRAM device' in s, ('Hardware configuration',f)
        assert sdk.exists(), ('Missing SDK build evidence',f)
        sdkconfig_sha256=hashlib.sha256(sdk.read_bytes()).hexdigest()
        flash_log=f.with_name(f.stem+'-flash.log').read_text(errors='replace')
        app_write=re.search(r'Wrote (\d+) bytes .* at 0x00010000.*\nHash of data verified\.',flash_log)
        if not app_write:
            raise ValueError('Missing verified app flash write '+str(f))
        image_bytes=int(app_write[1])
    rows=[(int(i),int(us),int(cyc)) for i,us,cyc in RUN.findall(s)]
    out=OUTPUT.search(s)
    if len(rows)!=30 or not out or 'CNN_DONE ' not in s or not START.search(s):raise ValueError('Truncated/incomplete log '+str(f))
    if [x[0] for x in rows]!=list(range(30)):raise ValueError('Indices wrong '+str(f))
    if not int(out.group(3)) or int(out.group(1))*2!=len(out.group(4)):raise ValueError('Unstable/bad output '+str(f))
    if any(x[1]<1 or x[2]<1 for x in rows):raise ValueError('Nonpositive time/cycles')
    h=2166136261
    for b in bytes.fromhex(out.group(4)):
        h=((h^b)*16777619)&0xffffffff
    if f'{h:08x}'!=out.group(2):raise ValueError('Incorrect output checksum '+str(f))
    a=re.search(r'arena_cap=(\d+) arena_used=(\d+)',s)
    stack=re.search(r'CNN_STACK high_water_bytes=(\d+)',s)
    return {'log':str(f),'arena_cap':int(a[1]) if a else None,'arena_used':int(a[2]) if a else None,
            'app_image_bytes':image_bytes,'sdkconfig_sha256':sdkconfig_sha256,
            'stack_high_water_bytes':int(stack[1]) if stack else None,'us':[r[1] for r in rows],'cycles':[r[2] for r in rows], 'output':out.group(4),'bytes':int(out.group(1))}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('log_root');ap.add_argument('--out',default='results/analysis/compare');args=ap.parse_args()
    root=Path(args.log_root);models=sorted(d for d in root.iterdir() if d.is_dir() and all((d/f'{v}-{b}.log').exists() for v in EXPECTED for b in (1,2)))
    if not models:raise SystemExit('No models with complete stock logs')
    report={'models':{},'failures':{},'warnings':['Built-in TFLM MEAN does not invoke ESP-NN global mean; EXP-MEAN effect MUST NOT be attributed to QACC without independent validated adapter + dispatch proof.']};csvrows=[]
    for modeldir in models:
        model=modeldir.name;items={}
        try:
            for variant in EXPECTED:
                items[variant]=[parse(modeldir/f'{variant}-{boot}.log') for boot in (1,2)]
        except (ValueError, AssertionError, FileNotFoundError) as error:
            report['failures'][model]={'error':str(error),'raw_partial':items}
            continue
        reference=items['stock'][0]['output']
        all_boots=[b for boots in items.values() for b in boots]
        if any(b['output']!=reference for b in all_boots):
            report['failures'][model]={'error':'EXACT OUTPUT MISMATCH','raw':items}
            continue
        if len({(b['arena_cap'],b['arena_used']) for b in all_boots})!=1:
            report['failures'][model]={'error':'Tensor arena varies by build','raw':items}
            continue
        if len({b['sdkconfig_sha256'] for b in all_boots})!=1 or any(
                len({b['app_image_bytes'] for b in boots})!=1 for boots in items.values()):
            report['failures'][model]={'error':'SDK configuration or per-variant image size varies by boot','raw':items}
            continue
        metadata=Path(__file__).resolve().parents[1]/'models'/model/'preflight.json'
        meta=json.loads(metadata.read_text()) if metadata.exists() else {}
        probe_log=Path(__file__).resolve().parents[1]/'results'/'diagnostics'/model/'combined-probe.log'
        probe_data=probe_log.read_text(errors='replace').rsplit('CAPTURE_RESET_SENT',1)[-1] if probe_log.exists() else ''
        pools=[int(x) for x in re.findall(r'sliding_rows=(\d+)',probe_data)]
        qacc=re.findall(r'CNN_QACC diagnostic_blocks=(\d+)',probe_data)
        qacc_ok=bool(qacc and int(qacc[-1])>0 and 'mismatches=0' in probe_data and (probe_log.parent.parent/'mean-bridge-qualified.txt').exists())
        baseline=statistics.median(statistics.median(b['us']) for b in items['stock'])
        baseline_cycles=statistics.median(statistics.median(b['cycles']) for b in items['stock'])
        report['models'][model]={'raw':items,'comparisons':{},'graph':meta,'sliding_calls_by_pool':pools,'qacc_verified':qacc_ok,'probe':str(probe_log) if probe_data else None}
        for v,boots in items.items():
            medus=statistics.median(statistics.median(b['us']) for b in boots)
            medcyc=statistics.median(statistics.median(b['cycles']) for b in boots)
            ratio=baseline/medus;cycratio=baseline_cycles/medcyc
            base=v=='stock'
            has_target=(v in ('opt2','combined') and any(pools)) or (v in ('mean','combined') and qacc_ok)
            paired=[100*(1-statistics.median(candidate['us'])/statistics.median(ref['us']))
                    for candidate,ref in zip(boots,items['stock'])]
            threshold='WIN' if 100*(1-medus/baseline)>1 else 'LOSS' if 100*(1-medus/baseline)<-1 else 'NEUTRAL'
            verdict='BASELINE' if base else threshold if has_target else ('CONTROL ONLY' if meta else threshold)
            if has_target and threshold in ('WIN','LOSS') and any(
                    gain <= 0 if threshold == 'WIN' else gain >= 0 for gain in paired):
                verdict='INCONCLUSIVE'
            data={'model':model,'variant':v,'baseline_us':baseline,'median_us':medus,'median_cycles':medcyc,
                  'baseline_cycles':baseline_cycles,'time_speedup':round(ratio,5),'cycle_speedup':round(cycratio,5),
                  'time_reduction_pct':round(100*(1-medus/baseline),3),'cycle_reduction_pct':round(100*(1-medcyc/baseline_cycles),3),
                  'verdict':verdict,'numerical_threshold':threshold,
                  'boots':2,'samples':sum(len(b['us']) for b in boots),'all_outputs_equal':True,
                  'min_us':min(min(b['us']) for b in boots),'max_us':max(max(b['us']) for b in boots),
                  'min_cycles':min(min(b['cycles']) for b in boots),'max_cycles':max(max(b['cycles']) for b in boots),
                  'boot1_median_us':statistics.median(boots[0]['us']),'boot2_median_us':statistics.median(boots[1]['us']),
                  'boot1_median_cycles':statistics.median(boots[0]['cycles']),'boot2_median_cycles':statistics.median(boots[1]['cycles']),
                  'boot1_time_reduction_pct':round(paired[0],5),'boot2_time_reduction_pct':round(paired[1],5),
                  'arena_cap':boots[0]['arena_cap'],'arena_used':boots[0]['arena_used'],
                  'app_image_bytes':boots[0]['app_image_bytes'],
                  'stack_high_water_bytes':min((b['stack_high_water_bytes'] for b in boots if b['stack_high_water_bytes'] is not None),default=None),
                  'mean_optimization_executed':qacc_ok if v in ('mean','combined') else False,
                  'sliding_pool_executed':bool(any(pools)) if v in ('opt2','combined') else False}
            csvrows.append(data);report['models'][model]['comparisons'][v]=data
            print(f'{model:30s} {v:8s} {medus:9.1f} us {medcyc:12.1f} cyc {ratio:7.3f}x {data["verdict"]}')
        comparisons=report['models'][model]['comparisons']
        report['models'][model]['combined_vs_individual']={}
        for v,active in (('opt2',qacc_ok),('mean',bool(any(pools)))):
            old,new=comparisons[v],comparisons['combined']
            delta=100*(1-new['median_us']/old['median_us'])
            boot_deltas=[100*(1-new[f'boot{boot}_median_us']/old[f'boot{boot}_median_us']) for boot in (1,2)]
            verdict='CONTROL ONLY'
            if active:
                verdict='NEUTRAL'
                if delta>1:
                    verdict='WIN' if min(boot_deltas)>0 else 'INCONCLUSIVE'
                elif delta<-1:
                    verdict='LOSS' if max(boot_deltas)<0 else 'INCONCLUSIVE'
            report['models'][model]['combined_vs_individual'][v]={
                'time_speedup':round(old['median_us']/new['median_us'],5),
                'cycle_speedup':round(old['median_cycles']/new['median_cycles'],5),
                'time_reduction_pct':round(delta,3),'boot_time_reduction_pct':boot_deltas,
                'additional_kernel_executed':active,'verdict':verdict}
    output=Path(args.out);output.parent.mkdir(parents=True,exist_ok=True)
    output.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
    with output.with_suffix('.csv').open('w',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=list(csvrows[0]) if csvrows else ['model','variant','verdict']);writer.writeheader();writer.writerows(csvrows)
    print('OUTPUT',output.with_suffix('.csv'),output.with_suffix('.json'))
    if report['failures']:
        print('FAILED VALIDATION', ', '.join(report['failures']),file=sys.stderr)
        sys.exit(1)
if __name__=='__main__':main()
