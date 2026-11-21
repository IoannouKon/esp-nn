import argparse
import pexpect

p = argparse.ArgumentParser()
p.add_argument("log")
p.add_argument("boots", type=int)
a = p.parse_args()
with open(a.log, "wb") as log:
    child = pexpect.spawn("idf.py", ["--ccache", "-B", "build-cnn", "-p", "/dev/ttyACM0", "flash", "monitor"], timeout=120)
    child.logfile_read = log
    try:
        for boot in range(a.boots):
            if boot:
                child.send(b"\x14\x12")
            matched = child.expect([rb"CNN_DONE\r*\n", b"CNN_ERROR", b"Guru Meditation", b"abort()", b"Task watchdog got triggered"])
            if matched:
                raise RuntimeError(f"board run failed, inspect {a.log}")
        child.send(b"\x1d")
        child.expect(pexpect.EOF, timeout=10)
    finally:
        child.close(force=True)
    if child.exitstatus:
        raise RuntimeError(f"monitor exit status {child.exitstatus}")
