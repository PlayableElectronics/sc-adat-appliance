#!/usr/bin/env python3
import os, socket, subprocess, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from mixerctl import controls, packet, parse_packet, read_config

config = "/workspace/payload/config/mixer.conf"
values, channels = read_config(config)
state = dict(controls(values, channels))
assert state["trim0"] == 1 and state["mute0"] == 0 and state["polarity0"] == 1
assert state["hpf0"] == 0 and state["group0_0"] == 1 and state["group0_1"] == 0
assert state["groupLevel0"] == 1 and state["master"] == 1 and state["bypass"] == 0
print("neutral controls, groups, mute, polarity, HPF-disabled, levels, bypass: OK")

proc = subprocess.Popen([sys.executable, os.path.join(os.path.dirname(__file__), "mixerctl.py"),
                         "serve", config, "--port", "57118", "--listen", "57121", "--no-node"],
                        stdout=None, stderr=None)
try:
    time.sleep(0.3)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.settimeout(2)
    sock.sendto(packet("/mixer/get", ",s", ["master"]), ("127.0.0.1", 57121))
    assert parse_packet(sock.recv(4096))[0] == "/mixer/state"
    sock.sendto(packet("/mixer/set", ",sf", ["master", 0.5]), ("127.0.0.1", 57121))
    assert parse_packet(sock.recv(4096))[0] == "/mixer/ok"
    sock.sendto(packet("/mixer/set", ",sf", ["master", float("nan")]), ("127.0.0.1", 57121))
    assert parse_packet(sock.recv(4096))[0] == "/mixer/error"
    print("OSC getter, setter, invalid NaN rejection: OK")
finally:
    proc.terminate(); proc.wait(timeout=2)
