#!/usr/bin/env python3
"""Fail-fast model preflight, including TFLM/ESP-NN eligibility estimates."""
import argparse,json,hashlib,sys
from pathlib import Path
import numpy as np
import tensorflow as tf
from tensorflow.lite.python import schema_py_generated as fb

def inspect(d):
    raw=(d/'model.tflite').read_bytes(); inp=(d/'input.bin').read_bytes()
    m=fb.Model.GetRootAsModel(raw,0); sg=m.Subgraphs(0)
    t=tf.lite.Interpreter(model_content=raw,num_threads=1); t.allocate_tensors()
    ins=t.get_input_details();outs=t.get_output_details()
    assert len(ins)==len(outs)==1,(len(ins),len(outs))
    a,b=ins[0],outs[0]
    assert a['dtype']==b['dtype']==np.int8,(a['dtype'],b['dtype'])
    assert int(np.prod(a['shape']))==len(inp), (a['shape'],len(inp))
    t.set_tensor(a['index'],np.frombuffer(inp,dtype=np.int8).reshape(a['shape']))
    t.invoke();out=t.get_tensor(b['index']).tobytes()
    ops=[];pools=[];means=[]
    for i in range(sg.OperatorsLength()):
        op=sg.Operators(i);ix=op.OpcodeIndex();code=m.OperatorCodes(ix).BuiltinCode()
        name=next((k for k,v in vars(fb.BuiltinOperator).items() if k.isupper() and v==code),str(code))
        if not isinstance(name,str):name=str(name)
        x=sg.Tensors(op.Inputs(0));shape=list(x.ShapeAsNumpy())
        ops.append(name)
        if code==fb.BuiltinOperator.MAX_POOL_2D:
            bo=op.BuiltinOptions();p=fb.Pool2DOptions();p.Init(bo.Bytes,bo.Pos)
            eligible=(len(shape)==4 and shape[-1]%16==0 and p.FilterWidth()==p.FilterHeight() and
                      p.FilterHeight() in (3,5) and p.StrideW()==p.StrideH()==1 and
                      p.Padding()==fb.Padding.SAME and shape[1]>=p.FilterHeight() and shape[2]>=p.FilterWidth())
            pools.append(dict(input_shape=shape,filter=[p.FilterHeight(),p.FilterWidth()],stride=[p.StrideH(),p.StrideW()],same=p.Padding()==fb.Padding.SAME,shape_eligible=eligible))
        if code==fb.BuiltinOperator.MEAN:
            means.append(dict(input_shape=shape, note='Builtin TFLM MEAN does NOT dispatch to ESP-NN.'))
    summary=dict(name=d.name,model_bytes=len(raw),input_shape=list(map(int,a['shape'])),output_shape=list(map(int,b['shape'])),input_dtype=str(a['dtype']),
        output_dtype=str(b['dtype']),ops=ops,pools=pools,means=means,model_sha256=hashlib.sha256(raw).hexdigest(),input_sha256=hashlib.sha256(inp).hexdigest(),
        host_output_sha256=hashlib.sha256(out).hexdigest(),host_output_hex=out.hex(),
        caveat='Eligible by shape is NOT runtime dispatch proof; validate alignment, tensor placement and call path on board.')
    (d/'preflight.json').write_text(json.dumps(summary,indent=2)+'\n');return summary

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('models_dir',nargs='?',default=str(Path(__file__).resolve().parents[1]/'models'));args=ap.parse_args()
    ok=0
    for d in sorted(Path(args.models_dir).iterdir()):
        if d.is_dir() and (d/'model.tflite').exists() and (d/'input.bin').exists():
            try:
                v=inspect(d);ok+=1
                print('READY',d.name,'bytes',v['model_bytes'],'max',len(v['pools']),'eligible',sum(p['shape_eligible'] for p in v['pools']),'MEAN',len(v['means']))
            except Exception as e:print('ERROR',d.name,repr(e));sys.exit(1)
    if not ok:sys.exit('No models found. Run prepare_models.sh / generate_models.py.')
