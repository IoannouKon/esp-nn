#!/usr/bin/env python3
"""Acquire pinned upstream pretrained INT8 CNN weights; never silently substitute.
Produces model.tflite/input.bin/metadata.json. No TensorFlow needed for acquisition.
With --preflight, run inspect_models.py separately in TensorFlow environment.
"""
import argparse,hashlib,json,sys,urllib.request
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
MODELS={m['name']:m for m in json.loads((ROOT/'PRETRAINED_MODELS.json').read_text())}

def acquire(item,force=False):
    d=ROOT/'models'/item['name'];d.mkdir(parents=True,exist_ok=True)
    path=d/'model.tflite'
    if not path.exists() or force:
        print('DOWNLOADING',item['name'],item['url'],flush=True)
        request=urllib.request.Request(item['url'],headers={'User-Agent':'esp-nn-multicnn-benchmark/1.0'})
        with urllib.request.urlopen(request,timeout=90) as response:
            blob=response.read(item['expected_size']+1024)
        if len(blob)!=item['expected_size']:
            raise RuntimeError(f'Unexpected size for {item["name"]}: {len(blob)} != {item["expected_size"]}')
        if blob[4:8]!=b'TFL3':raise RuntimeError('Not a valid TFLite FlatBuffer identifier TFL3')
        digest=hashlib.sha256(blob).hexdigest()
        if item['sha256'] is not None and digest!=item['sha256']:
            raise RuntimeError('SHA256 FAIL: expected '+item['sha256']+' got '+digest)
        path.write_bytes(blob)
    blob=path.read_bytes();sha=hashlib.sha256(blob).hexdigest()
    if len(blob)!=item['expected_size'] or blob[4:8]!=b'TFL3':raise RuntimeError('MODEL_INVALID '+item['name'])
    if item['sha256'] and sha!=item['sha256']:raise RuntimeError('MODEL_SHA256_FAIL '+item['name'])
    meta={**item,'actual_sha256':sha,'checked_published_sha256':bool(item['sha256'])}
    (d/'source_metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
    print('VERIFIED_DOWNLOAD',item['name'],len(blob),sha)

def fixed_input(model_dir):
    # Validate the immutable schema even when desktop TFLite rejects legacy bias metadata.
    from tensorflow.lite.python import schema_py_generated as fb
    raw=(model_dir/'model.tflite').read_bytes()
    graph=fb.Model.GetRootAsModel(raw,0).Subgraphs(0)
    if graph.InputsLength()!=1 or graph.OutputsLength()!=1:
        raise RuntimeError('Single input/output required')
    inp=graph.Tensors(graph.Inputs(0)); out=graph.Tensors(graph.Outputs(0))
    if inp.Type()!=fb.TensorType.INT8 or out.Type()!=fb.TensorType.INT8:
        raise RuntimeError('INT8 I/O required')
    shape=tuple(inp.Shape(i) for i in range(inp.ShapeLength()))
    if any(x<1 for x in shape):raise RuntimeError('Dynamic model input shape '+str(shape))
    # Avoid input with constant zeros only. Fixed raw INT8 values, 1 sample, no accuracy claim.
    rng=np.random.default_rng(20261121)
    values=rng.integers(-128,128,size=shape,dtype=np.int16).astype(np.int8)
    inpfile=model_dir/'input.bin'
    if inpfile.exists() and inpfile.read_bytes()!=values.tobytes():
        raise RuntimeError('Frozen input exists and differs, refusing to overwrite')
    inpfile.write_bytes(values.tobytes())
    sha=hashlib.sha256(values.tobytes()).hexdigest()
    (model_dir/'fixed_input.json').write_text(json.dumps(dict(shape=shape,dtype='int8',sha256=sha,kind='deterministic raw INT8 benchmark image/features; no accuracy claim',seed=20261121),indent=2)+'\n')
    print('FROZEN_INPUT',model_dir.name,shape,sha)

if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--list',action='store_true');p.add_argument('--all',action='store_true');p.add_argument('--optional',action='store_true')
    p.add_argument('--models',nargs='+',choices=MODELS);p.add_argument('--force',action='store_true')
    p.add_argument('--prepare-input',action='store_true',help='Requires tensorflow-cpu 2.15.1; generate frozen INT8 input')
    args=p.parse_args()
    if args.list:
        for v in MODELS.values():print(v['tier'],v['name'],v['title'],v['url'])
        sys.exit(0)
    names=args.models or ([m['name'] for m in MODELS.values() if args.optional or m['tier']=='core'] if args.all else [])
    if not names:p.error('Select --all or --models NAME ...')
    for name in names:
        acquire(MODELS[name],args.force)
        if args.prepare_input:fixed_input(ROOT/'models'/name)
