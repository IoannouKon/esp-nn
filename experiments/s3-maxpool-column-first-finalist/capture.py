#!/usr/bin/env python3
"""Capture raw USB-Serial/JTAG output from a verified ESP-IDF reset."""
import argparse
import hashlib
from pathlib import Path
import re
import time

from esp_pylib.serial_reset import hard_reset
import serial


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", type=Path)
    parser.add_argument("port")
    parser.add_argument("output", type=Path)
    parser.add_argument("--build-dir", type=Path)
    parser.add_argument("--timeout", type=float, default=900)
    args = parser.parse_args()
    build_dir = args.build_dir or args.app / "build"
    image = build_dir / (args.app.name + ".elf")
    expected = hashlib.sha256(image.read_bytes()).hexdigest().encode()
    done = (rb"^BENCH_DONE [^\r\n]+[\r\n]" if args.app.name == "bench_app"
            else rb"^TEST_RESULT: (?:PASS|FAIL)[\r\n]")
    port = serial.Serial(baudrate=115200, timeout=0.25, exclusive=True)
    port.dtr = False
    port.rts = False
    port.port = args.port
    data = bytearray()
    boot = False
    with args.output.open("xb") as output:
        with port:
            port.reset_input_buffer()
            output.write(b"CAPTURE_RESET_SENT\n")
            hard_reset(port, hold_delay=0.1)
            expire = time.monotonic() + args.timeout
            while time.monotonic() < expire:
                chunk = port.read(port.in_waiting or 1)
                if not chunk:
                    continue
                output.write(chunk)
                output.flush()
                data.extend(chunk)
                if not boot:
                    match = re.search(rb"ELF file SHA256:\s+([a-f0-9]+)", data)
                    if match:
                        if not expected.startswith(match[1]):
                            raise SystemExit(f"Unexpected firmware fingerprint in {args.output}")
                        boot = True
                if b"Guru Meditation" in data or b"watchdog got triggered" in data:
                    raise SystemExit(f"Firmware panic in {args.output}")
                if boot and re.search(done, data, re.M):
                    print("CAPTURE_PASS", args.output)
                    return
    raise SystemExit(f"No verified completion marker in {args.output}")


if __name__ == "__main__":
    main()
