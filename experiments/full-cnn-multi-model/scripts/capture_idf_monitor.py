#!/usr/bin/env python3
"""Capture ESP-IDF monitor using a PTY; reset after monitor attaches to avoid missing short tests."""
import argparse,os,pty,re,select,signal,subprocess,sys,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--app',required=True);p.add_argument('--port',default='/dev/ttyACM0');p.add_argument('--out',required=True);p.add_argument('--build',default='build');p.add_argument('--probe',action='store_true');p.add_argument('--timeout',type=int,default=1200);args=p.parse_args()
app=Path(args.app);out=Path(args.out);out.parent.mkdir(parents=True,exist_ok=True)
master,slave=pty.openpty()
proc=subprocess.Popen(['idf.py','-B',args.build,'-p',args.port,'monitor','--no-reset'],cwd=app,stdin=slave,stdout=slave,stderr=slave,start_new_session=True)
os.close(slave)
start=time.monotonic();deadline=start+args.timeout;reset_at=start+3;reset_sent=False;marker=False;buf=b'';failure=False
attached=False; tries=0
done=b'CNN_PROBE_DONE' if args.probe else b'CNN_DONE '
try:
    with out.open('wb') as log:
        while time.monotonic()<deadline:
            if not attached and re.search(rb'Help: Ctrl\+T followed by Ctrl\+H[^\n]*\n',buf):
                attached=True
                reset_at=time.monotonic()+1
            if attached and not reset_sent and time.monotonic()>=reset_at:
                tries+=1
                os.write(master,b'\x14\x12')  # IDF monitor Ctrl+T then Ctrl+R: hardware reset AFTER attach
                reset_sent=True
                reset_at=time.monotonic()+4
                buf=b''
                log.write(b'\nCAPTURE_RESET_SENT\n');log.flush()
            if reset_sent and b'ELF file SHA256:' not in buf and time.monotonic()>=reset_at:
                if tries>=3:
                    break
                reset_sent=False
            readable,_,_=select.select([master],[],[],0.25)
            if readable:
                try:chunk=os.read(master,8192)
                except OSError:break
                if not chunk:break
                log.write(chunk);log.flush();buf=(buf+chunk)[-131072:]
                if reset_sent and b'ELF file SHA256:' in buf and b'CNN_START ' in buf:marker=True
                if (marker or (reset_sent and b'ELF file SHA256:' in buf)) and (re.search(re.escape(done)+rb'[^\n]*\n',buf) or b'CNN_ERROR ' in buf):
                    failure=b'CNN_ERROR ' in buf and done not in buf
                    break
            if proc.poll() is not None:break
finally:
    try:os.write(master,b'\x1d') # quit ESP-IDF monitor via Ctrl+]
    except OSError:pass
    try:proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid,signal.SIGTERM)
        try:proc.wait(timeout=2)
        except subprocess.TimeoutExpired:os.killpg(proc.pid,signal.SIGKILL)
    os.close(master)
if not marker or done not in buf or failure:
    sys.exit(f'CAPTURE_FAILED (reset={reset_sent}, start={marker}, done={b"CNN_DONE " in buf}) log={out}')
print('CAPTURE_PASS',out)
