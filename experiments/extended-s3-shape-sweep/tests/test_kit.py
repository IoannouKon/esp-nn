"""Host-only smoke tests. No reported ESP32-S3 performance numbers."""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import shape_manifest as shapes
import compare_extended as cmp
from install_extended import install

class KitTests(unittest.TestCase):
    def test_manifest(self):
        manifest=shapes.generate(ROOT/'SHAPES.json')
        self.assertEqual(len(manifest['mean']),42)
        self.assertEqual(len(manifest['max_pool']),48)
        self.assertEqual(sum(x['opt_eligible'] for x in manifest['mean']),31)
        self.assertEqual(sum(x['opt_eligible'] for x in manifest['max_pool']),32)
        self.assertEqual(len(cmp.expected()),90)

    def test_install_and_preservation(self):
        with tempfile.TemporaryDirectory() as t:
            repo=Path(t)/'esp-nn';repo.mkdir()
            files={
                'bench_app/main/bench_main.c':
                  'static void bench_task(void *arg)\n{\n    bench_seed(BENCH_SEED);\n'
                  '    bench_conv();\n    bench_depthwise();\n    bench_fully_connected();\n'
                  '    bench_basic_math();\n    bench_pooling();\n    bench_activations();\n'
                  '    bench_softmax();\n    bench_mean();\n}\n',
                'bench_app/main/CMakeLists.txt':
                  'idf_component_register(SRCS "bench_main.c"\n                            "bench_softmax_mean.c"\n)',
                'bench_app/components/bench_harness/bench.c': 'UNMODIFIED VENDOR HARNESS\n',
                'src/pooling/esp_nn_max_pool_s8_esp32s3.c':'UNMODIFIED KERNEL\n'
            }
            for path,txt in files.items():
                f=repo/path;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(txt)
            subprocess.run(['git','init','-q',str(repo)],check=True)
            subprocess.run(['git','-C',str(repo),'add','.'],check=True)
            subprocess.run(['git','-C',str(repo),'-c','user.name=Test','-c','user.email=test@example.com',
                            'commit','-qm','fixture'],check=True)
            commit=subprocess.check_output(['git','-C',str(repo),'rev-parse','HEAD'],text=True).strip()
            result=install(repo,commit,False)
            self.assertEqual(result['git_sha'],commit)
            self.assertEqual((repo/'bench_app/components/bench_harness/bench.c').read_text(),files['bench_app/components/bench_harness/bench.c'])
            self.assertEqual((repo/'src/pooling/esp_nn_max_pool_s8_esp32s3.c').read_text(),'UNMODIFIED KERNEL\n')
            self.assertIn('bench_extended_mean', (repo/'bench_app/main/bench_main.c').read_text())
            self.assertEqual((repo/'bench_app/main/bench_extended_pool.c').read_text().count('BENCH_MEM_'),48) # all generated pool shapes
            self.assertIn('{ 63, 65, 16, BENCH_MEM_INT }',(repo/'bench_app/main/bench_extended_mean.c').read_text())
            with self.assertRaises(RuntimeError):install(repo,commit,False)

    def test_comparator_rejects_incomplete_and_mismatch(self):
        refs=cmp.expected()
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            def make(path,boost=1.0,bad=False):
                parts=['BENCH_START target=esp32s3 idf=v5.5.1-dirty cpu_mhz=240 psram=1 iters=9 seed=0xc0ffee42',
                       'EXTBENCH_VERSION=1 MEAN_CASES=42 POOL_CASES=48']
                for index,(op,shape,mem) in enumerate(sorted(refs)):
                    result='MISMATCH' if bad and index==0 else 'ok'
                    parts.append(f'BENCH op={op} variant=esp_nn mem={mem} ansi=2000 opt={int(1000/boost)} ratio=2.00 result={result} shape="{shape}"')
                parts.append('BENCH_DONE cases=90 failures=0 skipped=0')
                path.write_text('\n'.join(parts)+'\n')
            a=[root/f's-{i}.log' for i in (1,2)]
            b=[root/f'm-{i}.log' for i in (1,2)]
            c=[root/f'o-{i}.log' for i in (1,2)]
            for p in a:make(p)
            for p in b:make(p,boost=1.5)
            for p in c:make(p,boost=2)
            result=cmp.compare(a,b,c,root/'out')
            self.assertEqual(len(result['rows']),90)
            self.assertTrue((root/'out/RESULTS.md').exists())
            make(c[1],boost=2,bad=True)
            with self.assertRaises(cmp.ValidationError):cmp.compare(a,b,c,root/'out2')
            c[1].write_text('partial')
            with self.assertRaises(cmp.ValidationError):cmp.compare(a,b,c,root/'out3')

    def test_host_syntax_for_two_C_sources(self):
        with tempfile.TemporaryDirectory() as t:
            root=Path(t)
            (root/'bench_ops.h').write_text('''#pragma once
#include <stdint.h>
#include <stddef.h>
typedef enum { BENCH_MEM_INT, BENCH_MEM_EXT } bench_mem_t;
typedef void (*bench_fn)(void *,int,int8_t *);
typedef struct {const char *name; bench_fn call;} bench_variant_t;
typedef struct {const char *op,*shape;bench_mem_t mem;size_t out_size;
bench_fn ref;const bench_variant_t *variants;int n_variants;void *ctx;} bench_case_t;
void *bench_alloc(size_t,bench_mem_t);void bench_free(void *);
void bench_seed_case(const char *,const char *);void bench_fill(int8_t *,size_t);
void bench_skip(const char *,const char *,bench_mem_t);int bench_run(const bench_case_t *);
''')
            (root/'esp_nn.h').write_text('''#pragma once
#include <stdint.h>
int esp_nn_get_mean_scratch_size(int,int,int);
void esp_nn_set_mean_scratch_buf(void *);
void esp_nn_mean_nhwc_s8_ansi(const int8_t *,int8_t *,int,int,int,int,int,int,int);
void esp_nn_mean_nhwc_s8(const int8_t *,int8_t *,int,int,int,int,int,int,int);
void esp_nn_max_pool_s8_ansi(const int8_t *,int,int,int8_t *,int,int,int,int,int,int,int,int,int,int,int);
void esp_nn_max_pool_s8(const int8_t *,int,int,int8_t *,int,int,int,int,int,int,int,int,int,int,int);
''')
            data=json.loads((ROOT/'SHAPES.json').read_text())
            for kind, filename in [('mean','bench_extended_mean.c'),('pool','bench_extended_pool.c')]:
                tpl=(ROOT/'templates'/filename).read_text()
                if kind=='mean':
                    shapestr='\n'.join(f'{{ {x["h"]}, {x["w"]}, {x["ch"]}, BENCH_MEM_{x["mem"].upper()} }},' for x in data['mean'])
                else:
                    shapestr='\n'.join(f'{{ {x["w"]}, {x["h"]}, {x["ch"]}, {x["f"]}, {x["f"]}, {x["stride"]}, {x["pad"]}, BENCH_MEM_{x["mem"].upper()} }},' for x in data['max_pool'])
                tpl=tpl.replace('/* BEGIN_GENERATED_'+kind.upper()+' */\n/* END_GENERATED_'+kind.upper()+' */',shapestr)
                file=root/filename;file.write_text(tpl)
                subprocess.run(['gcc','-std=gnu11','-fsyntax-only','-Wall','-Wextra','-Werror','-I',str(root),str(file)],check=True,
                               capture_output=True,text=True)

if __name__=='__main__':unittest.main()
