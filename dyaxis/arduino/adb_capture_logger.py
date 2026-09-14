#!/usr/bin/env python3
"""Capture an Arduino ADB probe without toggling reset handshaking."""
import sys
import time
import serial

port = sys.argv[1] if len(sys.argv) > 1 else "/dev/ttyUSB0"
path = sys.argv[2] if len(sys.argv) > 2 else "adb-capture.log"
seconds = float(sys.argv[3]) if len(sys.argv) > 3 else 60.0

ser = serial.Serial()
ser.port = port
ser.baudrate = 115200
ser.timeout = 0.1
ser.dtr = False
ser.rts = False
ser.open()

end = time.monotonic() + seconds
with open(path, "wb", buffering=0) as out:
    while time.monotonic() < end:
        chunk = ser.read(512)
        if chunk:
            out.write(chunk)
ser.close()
