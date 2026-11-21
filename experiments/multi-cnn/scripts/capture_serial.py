#!/usr/bin/env python3
"""Reset via serial, capture raw logs, stop at CNN_DONE or CNN_ERROR, hard timeout."""
import argparse,time,sys
from pathlib import Path
import serial
p=argparse.ArgumentParser();p.add_argument('--port',default='/dev/ttyACM0');p.add_argument('--baud',type=int,default=115200);p.add_argument('--timeout',type=int,default=600);p.add_argument('--out',required=True); a=p.parse_args()
end=time.monotonic()+a.timeout
with serial.Serial(a.port,a.baud,timeout=.25) as s, open(a.out,'wb') as file:
    s.dtr=False;s.rts=True;time.sleep(.08);s.rts=False
    buf=b''
    while time.monotonic()<end:
        data=s.read(4096)
        if not data:continue
        file.write(data);file.flush();buf=(buf+data)[-12000:]
        if b'CNN_DONE ' in buf:
            print('CAPTURE_PASS',a.out);sys.exit(0)
        if b'CNN_ERROR ' in buf:
            print('CAPTURE_ERROR',a.out);sys.exit(2)
print('CAPTURE_TIMEOUT',a.out);sys.exit(3)
