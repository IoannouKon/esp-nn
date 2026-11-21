#!/usr/bin/env python3
"""Capture ESP-IDF monitor until BENCH_DONE, without a third-party Python package.

Requires an ESP-IDF environment where `idf.py` is available. Board must
already have been flashed. pty supplies the TTY required by idf_monitor.
"""
import argparse
import os
import pty
import re
import select
import signal
import subprocess
import sys
import time
from pathlib import Path

ANSI=re.compile(rb'\x1b\[[0-9;]*[A-Za-z]')

def run(cwd,port,output,limit):
    master,slave=pty.openpty()
    p=subprocess.Popen(['idf.py','-p',port,'monitor'],cwd=cwd,
                       stdin=slave,stdout=slave,stderr=slave,start_new_session=True)
    os.close(slave)
    start=time.monotonic(); stream=b''; started=False; done=False
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    try:
        with output.open('wb') as fp:
            while time.monotonic()-start < limit:
                if p.poll() is not None:break
                ready,_,_=select.select([master],[],[],0.4)
                if not ready:continue
                try:chunk=os.read(master,65536)
                except OSError:break
                if not chunk:break
                fp.write(chunk);fp.flush()
                sys.stdout.buffer.write(chunk);sys.stdout.buffer.flush()
                stream=(stream+ANSI.sub(b'',chunk))[-120000:]
                if b'BENCH_START' in stream:started=True
                if started and re.search(rb'BENCH_DONE\s+cases=\d+\s+failures=\d+\s+skipped=\d+',stream):
                    done=True;break
    finally:
        try:os.write(master,b'\x1d') # IDF monitor quit sequence
        except OSError:pass
        time.sleep(0.4)
        if p.poll() is None:
            try:os.killpg(p.pid,signal.SIGTERM)
            except ProcessLookupError:pass
        try:p.wait(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(p.pid,signal.SIGKILL);p.wait()
        os.close(master)
    if not done:
        sys.stderr.write(f'INCOMPLETE: no BENCH_START + BENCH_DONE within {limit}s; log {output}\n')
        return 1
    return 0

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cwd',type=Path,required=True)
    p.add_argument('--port',default='/dev/ttyACM0')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--timeout',type=int,default=1200)
    a=p.parse_args()
    sys.exit(run(a.cwd,a.port,a.output,a.timeout))
