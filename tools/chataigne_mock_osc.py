#!/usr/bin/env python3
"""Small dependency-free OSC mock for Chataigne project checks.

It validates the committed /mixer contract and replies with one state snapshot.
Run it on UDP 57120 while exercising the project, or import MockMixer in tests.
"""
from __future__ import annotations

import argparse
import math
import socket
import struct
from dataclasses import dataclass, field

GROUPS = ("kick", "drums", "bass", "music_a", "music_b", "vocals", "fx_a", "fx_b")
GROUP_KEYS = tuple(key for i in range(8) for key in (f"groupLevel{i}", f"group{i}PosX", f"group{i}PosY", f"group{i}Width", f"group{i}SpatialBypass"))
CAL_KEYS = tuple(f"quadOutput{n}{suffix}" for n in range(4) for suffix in ("GainDb", "Mute", "Polarity"))
SUPPORTED = set(GROUP_KEYS + CAL_KEYS + ("master",))


def _pad(value: bytes) -> bytes:
    return value + b"\0" * ((4 - len(value) % 4) % 4)


def osc_string(value: str) -> bytes:
    return _pad(value.encode() + b"\0")


def packet(path: str, types: str = "", values=()) -> bytes:
    out = osc_string(path) + osc_string("," + types)
    for typ, value in zip(types, values):
        if typ == "s": out += osc_string(str(value))
        elif typ == "f": out += struct.pack(">f", float(value))
        elif typ == "i": out += struct.pack(">i", int(value))
        else: raise ValueError(typ)
    return out


def _read_string(data: bytes, offset: int):
    end = data.index(b"\0", offset)
    return data[offset:end].decode(), (end + 4) & ~3


def parse(data: bytes):
    path, offset = _read_string(data, 0)
    types, offset = _read_string(data, offset)
    values = []
    for typ in types[1:]:
        if typ == "s": value, offset = _read_string(data, offset); values.append(value)
        elif typ == "f": values.append(struct.unpack(">f", data[offset:offset + 4])[0]); offset += 4
        elif typ == "i": values.append(struct.unpack(">i", data[offset:offset + 4])[0]); offset += 4
        else: raise ValueError(typ)
    return path, types, values


@dataclass
class MockMixer:
    state: dict[str, float | int] = field(default_factory=lambda: {
        **{key: 0.5 for key in GROUP_KEYS if key.endswith(("PosX", "PosY", "Width"))},
        **{f"groupLevel{i}": 1.0 for i in range(8)},
        **{f"group{i}SpatialBypass": 0 for i in range(8)},
        **{key: value for key, value in ((k, 0.0) for k in CAL_KEYS if k.endswith("GainDb"))},
        **{key: 0 for key in CAL_KEYS if key.endswith("Mute")},
        **{key: 1 for key in CAL_KEYS if key.endswith("Polarity")},
        "master": 1.0,
    })
    received: list[tuple[str, str, list]] = field(default_factory=list)
    sent: list[tuple[str, str, list]] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def handle(self, data: bytes) -> bytes:
        try:
            path, types, values = parse(data)
        except (ValueError, IndexError, UnicodeDecodeError) as exc:
            self.errors.append(f"malformed: {exc}")
            return packet("/mixer/error", "s", ["malformed OSC"])
        self.received.append((path, types, values))
        if path == "/mixer/get-all" and types == ",":
            for key, value in self.state.items(): self.sent.append(("/mixer/state", ",sf", [key, value]))
            self.sent.append(("/mixer/get-all-done", ",", []))
            return packet("/mixer/get-all-done")
        if path == "/mixer/set" and types == ",sf" and len(values) == 2:
            key, value = values
            if key not in SUPPORTED or not math.isfinite(float(value)):
                self.errors.append(f"unsupported key: {key}")
                return packet("/mixer/error", "s", [f"unsupported key: {key}"])
            self.state[key] = value
            self.sent.append(("/mixer/ok", ",s", [key]))
            return packet("/mixer/ok", "s", [key])
        self.errors.append(f"unexpected: {path} {types}")
        return packet("/mixer/error", "s", ["unexpected message"])


def serve(host: str, port: int) -> None:
    mixer = MockMixer()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((host, port))
    print(f"mock mixer listening on {host}:{port}", flush=True)
    while True:
        data, address = sock.recvfrom(65535)
        reply = mixer.handle(data)
        sock.sendto(reply, address)
        while mixer.sent:
            path, types, values = mixer.sent.pop(0)
            sock.sendto(packet(path, types[1:], values), address)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=57120)
    args = parser.parse_args()
    serve(args.host, args.port)
