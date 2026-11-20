#!/usr/bin/env python3
"""Compare unmodified ESP-NN BENCH logs; external analysis only.

Reads all BENCH_START/BENCH/BENCH_DONE blocks and compares optimized cycles
for the same operation, variant, memory placement and shape. Never changes the
official benchmark application or its measurement method.
"""
import argparse
import json
import re
import statistics
from collections import defaultdict
from pathlib import Path

START = re.compile(r'^BENCH_START\s+(.*)$')
DONE = re.compile(r'^BENCH_DONE\s+(.*)$')
ROW = re.compile(r'^BENCH\s+op=(\S+)\s+variant=(\S+)\s+mem=(\S+)\s+ansi=(\d+)\s+opt=(\d+)\s+ratio=(\S+)\s+result=(\S+)\s+shape="([^"]*)"')
KV = re.compile(r'(\w+)=([^\s]+)')


def clean(line):
    line = re.sub(r'\x1b\[[0-9;]*[A-Za-z]', '', line).strip()
    # Support monitor timestamps or log prefixes; line must contain BENCH marker.
    i = line.find('BENCH')
    return line[i:] if i >= 0 else line


def read_runs(path):
    text = Path(path).read_text(encoding='utf-8', errors='replace')
    runs = []
    active = None
    for raw in text.splitlines():
        line = clean(raw)
        m = START.match(line)
        if m:
            if active is not None:
                raise ValueError(f'{path}: BENCH_START encountered without prior BENCH_DONE')
            active = {'config': dict(KV.findall(m.group(1))), 'rows': {}, 'warnings': [], 'done': None}
            continue
        if active is None:
            continue
        d = DONE.match(line)
        if d:
            active['done'] = dict(KV.findall(d.group(1)))
            for field in ('failures', 'skipped'):
                if active['done'].get(field) != '0':
                    raise ValueError(f'{path}: {field}={active["done"].get(field)}')
            runs.append(active)
            active = None
            continue
        if line.startswith('BENCH_WARN'):
            active['warnings'].append(line)
            continue
        r = ROW.match(line)
        if r:
            op, variant, mem, ansi, opt, ratio, result, shape = r.groups()
            if result != 'ok':
                raise ValueError(f'{path}: non-ok result: {line}')
            key = (op, variant, mem, shape)
            if key in active['rows']:
                raise ValueError(f'{path}: duplicate row {key} within one run')
            active['rows'][key] = {'opt': int(opt), 'ansi': int(ansi)}
    if active is not None:
        raise ValueError(f'{path}: log ends without BENCH_DONE')
    if not runs:
        raise ValueError(f'{path}: no complete BENCH_START..BENCH_DONE found')
    rowset = set(runs[0]['rows'])
    for r in runs:
        if set(r['rows']) != rowset:
            raise ValueError(f'{path}: benchmark row keys differ across boots')
        if r['config'] != runs[0]['config']:
            raise ValueError(f'{path}: benchmark config differs across boots')
    return runs


def compare(stock, cand):
    if stock[0]['config'] != cand[0]['config']:
        raise ValueError('stock/candidate BENCH_START configuration differs')
    a, b = set(stock[0]['rows']), set(cand[0]['rows'])
    if a != b:
        raise ValueError('stock/candidate timed rows differ: missing=%s extra=%s' % (sorted(a-b), sorted(b-a)))
    if stock[0]['done'].get('cases') != cand[0]['done'].get('cases'):
        raise ValueError('stock/candidate total BENCH_DONE cases differ')
    rows = []
    for key in sorted(a):
        s = [r['rows'][key]['opt'] for r in stock]
        c = [r['rows'][key]['opt'] for r in cand]
        sm = statistics.median(s)
        cm = statistics.median(c)
        rows.append(dict(op=key[0], variant=key[1], mem=key[2], shape=key[3],
                         stock_cycles=s, candidate_cycles=c,
                         stock_median=sm, candidate_median=cm,
                         speedup=sm/cm if cm > 0 else None,
                         reduction_percent=100*(sm-cm)/sm if sm > 0 else None,
                         delta_cycles=cm-sm,
                         ranges_overlap=not (max(s)<min(c) or max(c)<min(s))))
    return dict(config=stock[0]['config'], stock_runs=len(stock), candidate_runs=len(cand),
                stock_warnings=[w for r in stock for w in r['warnings']],
                candidate_warnings=[w for r in cand for w in r['warnings']],
                rows=rows)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--stock', required=True)
    ap.add_argument('--candidate', required=True)
    ap.add_argument('--output', required=True)
    args=ap.parse_args()
    result=compare(read_runs(args.stock), read_runs(args.candidate))
    path=Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result,indent=2)+'\n')
    print('Complete runs: stock=%s candidate=%s rows=%s' % (result['stock_runs'],result['candidate_runs'],len(result['rows'])))
    print('Every parsed BENCH row had result=ok; every BENCH_DONE had failures=0 skipped=0.')
    print('Results by operation:')
    for row in result['rows']:
        if row['op']=='mean':
            print('%-32s mem=%-3s stock=%8s candidate=%8s speedup=%.4fx reduction=%+.2f%%' %
                (row['shape'], row['mem'], row['stock_median'], row['candidate_median'],
                 row['speedup'],row['reduction_percent']))
    changes=[r for r in result['rows'] if r['delta_cycles'] != 0]
    print('Changed rows across complete suite:',len(changes))
    print('Full comparison:',path)


if __name__=='__main__':
    main()
