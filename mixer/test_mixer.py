#!/usr/bin/env python3
import os, socket, subprocess, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from mixerctl import GROUPS, controls, packet, parse_packet, read_config

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

# Actual sample-flow test: the scan SynthDef writes simulated hardware input
# buses 26..41. The mixer must read those buses and emit only output buses 0..15.
proc = subprocess.Popen([sys.executable, os.path.join(os.path.dirname(__file__), "mixerctl.py"),
                         "serve", config, "--port", "57118", "--listen", "57121"],
                        stdout=None, stderr=None)
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.settimeout(2)
time.sleep(0.5)
def meters():
    sock.sendto(packet("/mixer/meters", ","), ("127.0.0.1", 57121))
    return parse_packet(sock.recv(4096))[2]
def inject(input_bus):
    sock.sendto(packet("/s_new", ",siiisisfsfsi",
                       ["sc_adat_scan", 3100, 0, 0, "output", input_bus,
                        "freq", 440.0, "level", -30.0, "gate", 1]),
                ("127.0.0.1", 57118))
    time.sleep(0.6)
try:
    for channel in (1, 9, 16):
        values = meters()
        assert max(float(x) for x in values) < 0.01
        inject(26 + channel - 1)
        values = [float(x) for x in meters()]
        input_peaks, group_peaks, output_peaks = values[:16], values[32:40], values[48:64]
        assert input_peaks[channel - 1] > 0.01
        assert output_peaks[channel - 1] > 0.01
        assert all(x < 0.01 for i,x in enumerate(input_peaks) if i != channel - 1)
        assert all(x < 0.01 for i,x in enumerate(output_peaks) if i != channel - 1)
        expected_group = GROUPS.index(channels[channel - 1]["group"])
        assert group_peaks[expected_group] > 0.01, (channel, input_peaks, group_peaks, output_peaks)
        assert all(x < 0.01 for i,x in enumerate(group_peaks) if i != expected_group)
        sock.sendto(packet("/n_set", ",isi", [3100, "gate", 0]), ("127.0.0.1", 57118))
        time.sleep(0.4)
    inject(42)  # physical channel 17: outside the active 16-channel window
    values = [float(x) for x in meters()]
    assert max(values[:16] + values[48:64]) < 0.01
    print("sample flow buses 26->0, 34->8, 41->15; meters and channels 17..26: OK")
finally:
    proc.terminate(); proc.wait(timeout=2)
