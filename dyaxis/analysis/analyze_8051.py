#!/usr/bin/env python3
"""Small, dependency-free first-pass analyzer for an 8051-family ROM image.

This intentionally does not disassemble every opcode.  It reports stable,
reproducible evidence useful before choosing a full reverse-engineering tool:
vector targets, common 8051 SFR-immediate operations, printable strings, and
simple byte statistics.  It never writes to the input image.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import pathlib
import re
from collections import Counter

EXPECTED_SIZE = 32_768

SFR_NAMES = {
    0x80: "P0", 0x81: "SP", 0x82: "DPL", 0x83: "DPH", 0x87: "PCON",
    0x88: "TCON", 0x89: "TMOD", 0x8A: "TL0", 0x8B: "TL1",
    0x8C: "TH0", 0x8D: "TH1", 0x90: "P1", 0x98: "SCON", 0x99: "SBUF",
    0xA0: "P2", 0xA8: "IE", 0xB0: "P3", 0xB8: "IP", 0xC8: "T2CON",
    0xCA: "RCAP2L", 0xCB: "RCAP2H", 0xCC: "TL2", 0xCD: "TH2",
    0xD0: "PSW", 0xE0: "ACC", 0xF0: "B",
}

VECTOR_NAMES = [
    (0x0000, "reset"), (0x0003, "external interrupt 0"),
    (0x000B, "timer 0 overflow"), (0x0013, "external interrupt 1"),
    (0x001B, "timer 1 overflow"), (0x0023, "serial RI/TI"),
    (0x002B, "timer 2 / capture"),
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def printable_runs(data: bytes, minimum: int = 4):
    pattern = rb"[\x20-\x7e]{%d,}" % minimum
    return [(m.start(), m.group().decode("ascii")) for m in re.finditer(pattern, data)]


def vectors(data: bytes):
    rows = []
    for address, name in VECTOR_NAMES:
        op = data[address]
        if op == 0x02 and address + 2 < len(data):  # LJMP addr16
            target = (data[address + 1] << 8) | data[address + 2]
            rows.append((address, name, f"LJMP 0x{target:04X}"))
        else:
            rows.append((address, name, f"inline opcode 0x{op:02X}"))
    return rows


def sfr_immediates(data: bytes):
    rows = []
    for offset in range(len(data) - 2):
        if data[offset] == 0x75:  # MOV direct,#immediate
            sfr = data[offset + 1]
            if sfr in SFR_NAMES:
                rows.append((offset, SFR_NAMES[sfr], sfr, data[offset + 2]))
    return rows


def entropy(data: bytes) -> float:
    counts = Counter(data)
    return -sum((n / len(data)) * math.log2(n / len(data)) for n in counts.values())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("image", type=pathlib.Path)
    args = parser.parse_args()
    data = args.image.read_bytes()
    if len(data) != EXPECTED_SIZE:
        raise SystemExit(f"size mismatch: {len(data)} != {EXPECTED_SIZE}")

    print(f"image: {args.image}")
    print(f"size: {len(data)} bytes")
    print(f"sha256: {sha256(data)}")
    print(f"entropy: {entropy(data):.3f} bits/byte")
    print(f"zero_bytes: {data.count(0x00)}")
    print(f"ff_bytes: {data.count(0xFF)}")
    print("top_bytes: " + ", ".join(f"0x{k:02X}={v}" for k, v in Counter(data).most_common(12)))

    print("\n8051 vector table:")
    for address, name, target in vectors(data):
        print(f"  0x{address:04X} {name}: {target}")

    print("\ncommon SFR immediate writes (offset, register, value):")
    for offset, name, sfr, value in sfr_immediates(data):
        print(f"  0x{offset:04X}: MOV {name}(0x{sfr:02X}),#0x{value:02X}")

    print("\nprintable strings:")
    for offset, text in printable_runs(data):
        print(f"  0x{offset:04X}: {text}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
