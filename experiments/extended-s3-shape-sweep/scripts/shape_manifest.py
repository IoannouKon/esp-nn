#!/usr/bin/env python3
"""Checked-in, deterministic shape plan for ESP32-S3 extended benchmarks."""
from dataclasses import dataclass, asdict
import json
from pathlib import Path

@dataclass(frozen=True)
class Mean:
    h:int; w:int; ch:int; mem:str
    @property
    def eligible(self): return self.h*self.w <= 4095 and self.ch >= 16 and self.ch % 16 == 0
    @property
    def shape(self): return f'input {self.h}x{self.w}x{self.ch}'

@dataclass(frozen=True)
class Pool:
    w:int; h:int; ch:int; f:int; stride:int; pad:int; mem:str
    @property
    def eligible(self):
        return (self.f in (3,5) and self.stride==1 and self.pad==self.f//2
                and self.ch%16==0 and self.w>=self.f and self.h>=self.f)
    @property
    def shape(self):return f'input {self.w}x{self.h}x{self.ch}, filter {self.f}x{self.f}, pad {self.pad}, stride {self.stride}'

MEAN = [
    Mean(7,7,16,'int'),Mean(14,14,120,'int'), # original official cases
    Mean(1,1,16,'int'),Mean(2,2,16,'int'),Mean(3,3,16,'int'),Mean(4,4,16,'int'),
    Mean(7,7,32,'int'),Mean(7,7,64,'int'),Mean(7,7,128,'int'),Mean(7,7,256,'int'),
    Mean(14,14,16,'int'),Mean(14,14,32,'int'),Mean(14,14,64,'int'),Mean(14,14,128,'int'),
    Mean(28,28,16,'int'),Mean(28,28,32,'int'),Mean(28,28,64,'int'),
    Mean(32,32,16,'int'),Mean(32,32,32,'int'),Mean(32,32,64,'int'),
    Mean(63,65,16,'int'), # 4095 == QACC saturation bound
    Mean(64,64,16,'int'), # 4096 scalar fallback
    Mean(8,8,8,'int'),Mean(8,8,12,'int'),Mean(8,8,15,'int'),
    Mean(8,8,17,'int'),Mean(8,8,24,'int'),Mean(8,8,31,'int'),Mean(8,8,33,'int'),
    Mean(14,14,120,'ext'),Mean(14,14,128,'ext'),
    Mean(7,7,16,'ext'),Mean(7,7,32,'ext'),Mean(7,7,64,'ext'),
    Mean(28,28,32,'ext'),Mean(28,28,64,'ext'),
    Mean(32,32,128,'ext'),Mean(64,64,16,'ext'),Mean(63,65,16,'ext'),
    Mean(1,256,16,'int'),Mean(1,256,64,'int'),Mean(1,1024,16,'ext'),
]
POOL = [
    Pool(16,16,16,3,1,1,'int'),Pool(12,12,128,5,1,2,'ext'), # official shapes
    Pool(4,4,16,3,1,1,'int'),Pool(5,5,16,3,1,1,'int'),
    Pool(7,7,16,3,1,1,'int'),Pool(8,8,16,3,1,1,'int'),
    Pool(16,16,32,3,1,1,'int'),Pool(16,16,64,3,1,1,'int'),
    Pool(16,16,128,3,1,1,'int'),Pool(32,32,16,3,1,1,'int'),
    Pool(32,32,32,3,1,1,'int'),Pool(32,32,64,3,1,1,'int'),
    Pool(24,24,128,3,1,1,'ext'),Pool(32,32,128,3,1,1,'ext'),
    Pool(64,64,16,3,1,1,'ext'),Pool(64,64,32,3,1,1,'ext'),
    Pool(6,6,16,5,1,2,'int'),Pool(7,7,16,5,1,2,'int'),
    Pool(12,12,16,5,1,2,'int'),Pool(12,12,32,5,1,2,'int'),
    Pool(12,12,64,5,1,2,'int'),Pool(12,12,128,5,1,2,'int'),
    Pool(16,16,16,5,1,2,'int'),Pool(16,16,64,5,1,2,'int'),
    Pool(24,24,64,5,1,2,'ext'),Pool(32,32,128,5,1,2,'ext'),
    Pool(64,64,16,5,1,2,'ext'),
    Pool(16,16,8,3,1,1,'int'),Pool(16,16,12,3,1,1,'int'),
    Pool(16,16,15,3,1,1,'int'),Pool(16,16,24,3,1,1,'int'),
    Pool(16,16,31,3,1,1,'int'),Pool(16,16,48,5,1,2,'int'),
    Pool(16,16,120,5,1,2,'int'),
    Pool(16,16,16,2,2,0,'int'),Pool(16,16,32,2,2,0,'int'),
    Pool(32,32,64,2,2,0,'ext'),Pool(32,32,128,2,2,0,'ext'),
    Pool(16,16,16,3,2,1,'int'),Pool(16,16,64,3,2,1,'int'),
    Pool(16,16,16,3,1,0,'int'),Pool(16,16,32,5,1,0,'int'),
    Pool(2,2,16,3,1,1,'int'),Pool(4,4,16,5,1,2,'int'),
    Pool(16,16,16,3,1,1,'ext'),Pool(16,16,32,3,1,1,'ext'),
    Pool(16,16,64,5,1,2,'ext'),Pool(32,32,16,5,1,2,'ext'),
]

def check():
    for group,name in [(MEAN,'mean'),(POOL,'max_pool')]:
        keys=set()
        for x in group:
            k=(x.shape,x.mem)
            if k in keys:raise ValueError(f'Duplicate {name}: {k}')
            keys.add(k)
            if name=='max_pool':
                assert (x.w+2*x.pad-x.f)//x.stride+1 > 0
                assert (x.h+2*x.pad-x.f)//x.stride+1 > 0
            assert x.mem in ('int','ext')


def generate(dst:Path):
    check()
    dst.parent.mkdir(parents=True,exist_ok=True)
    data={
      'version':1,
      'mean':[dict(asdict(x),shape=x.shape,opt_eligible=x.eligible) for x in MEAN],
      'max_pool':[dict(asdict(x),shape=x.shape,opt_eligible=x.eligible) for x in POOL],
      'notes': 'Eligibility presumes 16-byte aligned disjoint input/output allocations from Espressif bench_harness. Optimize-path eligibility is based on inspected v1.5.0 experiment dispatch; verification on board is separate.'
    }
    dst.write_text(json.dumps(data,indent=2)+'\n')
    return data

if __name__=='__main__':
    d=generate(Path(__file__).resolve().parents[1]/'SHAPES.json')
    for k in ('mean','max_pool'):
        print(k,len(d[k]),'eligible',sum(x['opt_eligible'] for x in d[k]))
