#!/usr/bin/env python3
"""Real scsynth check for one ordered stereo source (run inside the gate)."""
import math
import os
import re
import socket
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(__file__))
from mixerctl import packet, parse_packet, read_config

ROOT = os.path.dirname(os.path.dirname(__file__))
base_path = "/workspace/payload/config/mixer.conf"
base = open(base_path, encoding="utf-8").read()
canonical_values, _ = read_config(base_path)
canonical_sources = canonical_values["_sources"]
assert len(canonical_sources) == 16 and all(source.mode == "mono" for source in canonical_sources)
lines = [line for line in base.splitlines() if not re.match(r"^(source_map_version|source\.count|source\.\d+\.)", line)]
lines += ["source_map_version=1", "source.count=15"]
lines += ["source.1.id=stereo_pair", "source.1.name=Stereo Pair", "source.1.mode=stereo", "source.1.inputs=1,2", "source.1.group=music_a"]
for index, source in enumerate(canonical_sources[2:], 2):
    physical = source.inputs[0]
    lines += [f"source.{index}.id={source.id}", f"source.{index}.name={source.name}", f"source.{index}.mode=mono", f"source.{index}.inputs={physical}", f"source.{index}.group={source.group}"]
scene = "\n".join(lines) + "\n"
scene = re.sub(r"(?m)^master\.level_db=.*$", "master.level_db=0", scene)
scene = scene.replace("channel.1.group=kick", "channel.1.group=music_a").replace("channel.2.group=drums", "channel.2.group=music_a")
with tempfile.NamedTemporaryFile("w", suffix=".conf", delete=False) as fixture:
    fixture.write(scene)
    config = fixture.name
values, channels = read_config(config)
assert values["_sources"][0].mode == "stereo" and values["_sources"][0].inputs == (1, 2)

server = subprocess.Popen([sys.executable, os.path.join(ROOT, "mixer/mixerctl.py"), "serve", config, "--port", "57118", "--listen", "57123", "--mode", "stereo"])
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(1)
SC = ("127.0.0.1", 57118)
MIXER = ("127.0.0.1", 57123)


def sync(token):
    sock.sendto(packet("/sync", ",i", [token]), SC)
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if parse_packet(sock.recv(65535))[0] == "/synced":
            return
    raise AssertionError("mixed-source scsynth sync timeout")


def set_mixer(key, value):
    sock.sendto(packet("/mixer/set", ",sf", [key, value]), MIXER)
    while True:
        reply = parse_packet(sock.recv(65535))
        if reply[0] in ("/mixer/ok", "/mixer/error"):
            assert reply[0] == "/mixer/ok", reply
            return


def meters():
    sock.sendto(packet("/mixer/meters", ","), MIXER)
    while True:
        reply = parse_packet(sock.recv(65535))
        if reply[0] == "/mixer/meters":
            values = [float(value) for value in reply[2]]
            assert len(values) == 80 and all(math.isfinite(value) for value in values)
            return values[48:64]


def inject(bus, node):
    sock.sendto(packet("/s_new", ",siiisisfsfsi", ["sc_adat_scan", node, 0, 0, "output", bus, "freq", 440.0, "level", -24.0, "gate", 1]), SC)
    sync(node)
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        peaks = meters()
        if max(peaks[:2]) > 0.01:
            return
    raise AssertionError(("stereo source did not reach output", meters()))


def stop(node):
    sock.sendto(packet("/n_set", ",isf", [node, "gate", 0.0]), SC)
    sync(node + 1000)
    time.sleep(0.15)
    sock.sendto(packet("/n_free", ",i", [node]), SC)
    sync(node + 2000)


try:
    time.sleep(0.5)
    set_mixer("group3PosX", 0.5)
    set_mixer("group3PosY", 0.5)
    set_mixer("group3Width", 0.0)
    inject(26, 9800)
    left_only = meters()
    assert left_only[0] > 0.01 and left_only[1] < 0.005, left_only
    stop(9800)
    inject(27, 9801)
    right_only = meters()
    assert right_only[1] > 0.01 and right_only[0] < 0.005, right_only
    stop(9801)
    print("real mixed source audio: ordered stereo L/R preservation and group routing: OK")
finally:
    server.terminate()
    server.wait(timeout=2)
    sock.close()
    os.unlink(config)
