#!/usr/bin/env python3
"""Install ONLY extended benchmark sources into a disposable ESP-NN worktree.

Keeps stock bench_app/main/bench_pooling.c, bench_softmax_mean.c, and
bench_harness/bench.c untouched. Never edits kernel source.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
MARK='/* ESP-NN EXTENDED S3 EXPERIMENT V1 */'

def require(cond,message):
    if not cond:raise RuntimeError(message)

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def git(path,*cmd):
    return subprocess.check_output(['git','-C',str(path),*cmd],text=True).strip()

def install(repo:Path,expected_ref:str,allow_dirty:bool):
    repo=repo.resolve()
    require((repo/'bench_app/main/bench_main.c').is_file(),'Missing ESP-NN bench app')
    require(git(repo,'rev-parse','HEAD')==git(repo,'rev-parse',expected_ref),
            f'Wrong HEAD; expected {expected_ref}, got {git(repo,"rev-parse","HEAD")}')
    dirty=git(repo,'status','--porcelain')
    require(not dirty or allow_dirty, f'Worktree is dirty before install: {dirty}')
    main=repo/'bench_app/main'
    src=main/'bench_main.c'
    cmake=main/'CMakeLists.txt'
    s=src.read_text()
    cm=cmake.read_text()
    require(MARK not in s,'Already installed: do not install twice')
    require('bench_extended_mean.c' not in cm,'CMake already modified')
    # Strictly preserve all official source/harness files; only redirect
    # the app's run sequence to the two extended sweeps.
    anchor='    bench_seed(BENCH_SEED);'
    require(s.count(anchor)==1,'Cannot locate official bench_seed call')
    s=s.replace(anchor,anchor+'\n    printf("EXTBENCH_VERSION=1 MEAN_CASES=42 POOL_CASES=48\\n");')
    original='''    bench_conv();
    bench_depthwise();
    bench_fully_connected();
    bench_basic_math();
    bench_pooling();
    bench_activations();
    bench_softmax();
    bench_mean();'''
    require(s.count(original)==1,'Unknown upstream bench_main sequence')
    s=s.replace(original,'    bench_extended_mean();\n    bench_extended_pooling();')
    insert_before='static void bench_task(void *arg)'
    require(insert_before in s,'Unknown upstream main declarations')
    s=s.replace(insert_before,MARK+'\nvoid bench_extended_mean(void);\nvoid bench_extended_pooling(void);\n\n'+insert_before)
    anchor='                            "bench_softmax_mean.c"'
    require(cm.count(anchor)==1,'Unknown upstream CMake source list')
    cm=cm.replace(anchor,anchor+'\n                            "bench_extended_mean.c"\n                            "bench_extended_pool.c"')
    manifest=json.loads((ROOT/'SHAPES.json').read_text())
    replacements={
        'mean':('\n'.join(f'    {{ {x["h"]}, {x["w"]}, {x["ch"]}, BENCH_MEM_{x["mem"].upper()} }},'
                         for x in manifest['mean'])),
        'pool':('\n'.join(f'    {{ {x["w"]}, {x["h"]}, {x["ch"]}, {x["f"]}, {x["f"]}, {x["stride"]}, {x["pad"]}, BENCH_MEM_{x["mem"].upper()} }},'
                         for x in manifest['max_pool']))
    }
    for name,source in [('mean','bench_extended_mean.c'),('pool','bench_extended_pool.c')]:
        f=(ROOT/'templates'/source).read_text()
        open_token=f'/* BEGIN_GENERATED_{name.upper()} */'
        end_token=f'/* END_GENERATED_{name.upper()} */'
        require(f.count(open_token)==1 and f.count(end_token)==1,'Template markers missing')
        f=f.replace(open_token+'\n'+end_token, replacements[name])
        (main/source).write_text(f)
    src.write_text(s)
    cmake.write_text(cm)
    out={
      'repo':str(repo), 'git_sha':git(repo,'rev-parse','HEAD'),
      'benchmark_files':{
        str(p.relative_to(repo)):sha(p)
        for p in (src,cmake,main/'bench_extended_mean.c',main/'bench_extended_pool.c')},
      'untouched_harness_sha256':sha(repo/'bench_app/components/bench_harness/bench.c'),
      'manifest_sha256':sha(ROOT/'SHAPES.json')
    }
    print(json.dumps(out,indent=2))
    return out

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',required=True,type=Path)
    p.add_argument('--ref',required=True,help='Exact Git SHA to require at HEAD')
    p.add_argument('--allow-dirty',action='store_true',help='Only when existing edits are well understood')
    a=p.parse_args()
    install(a.repo,a.ref,a.allow_dirty)
