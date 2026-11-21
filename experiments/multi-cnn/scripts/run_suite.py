#!/usr/bin/env python3
"""Flash the selected built image and capture one fresh reset in an IDF monitor."""
import argparse
from pathlib import Path
from subprocess import run

import pexpect

parser = argparse.ArgumentParser()
parser.add_argument("app", type=Path)
parser.add_argument("build")
parser.add_argument("log", type=Path)
parser.add_argument("--port", default="/dev/ttyACM0")
args = parser.parse_args()
args.log = args.log.resolve()
args.log.parent.mkdir(parents=True, exist_ok=True)
cmd = ["idf.py", "--ccache", "-B", args.build, "-p", args.port]
with args.log.with_suffix(".flash.log").open("wb") as flash_log:
    run(cmd + ["flash"], cwd=args.app, stdout=flash_log, stderr=flash_log, check=True)
with args.log.open("wb") as serial_log:
    monitor = pexpect.spawn(cmd[0], cmd[1:] + ["monitor"], cwd=str(args.app),
                            timeout=1200, maxread=8192)
    monitor.logfile_read = serial_log
    try:
        found = monitor.expect(rb"CNN_SUITE_DONE\r*\n|CNN_FATAL[^\n]*\n|Guru Meditation")
        assert monitor.match.group(0).startswith(b"CNN_SUITE_DONE"), monitor.match.group(0)
        monitor.send(b"\x1d")
        monitor.expect(pexpect.EOF, timeout=5)
    finally:
        monitor.close(force=True)
print(args.log)
