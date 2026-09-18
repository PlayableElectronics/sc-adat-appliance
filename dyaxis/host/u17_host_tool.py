#!/usr/bin/env python3
"""Receive-only U17 capture and one-shot probe harness.

The current U17 ROM evidence does not recover a wire packet, so every built-in
candidate deliberately has unknown wire bytes and is refused by probe mode.
Transmission requires --transmit and an exact candidate definition with bytes.
This module never retries or runs a background transmitter.
"""

from __future__ import annotations

import argparse
import json
import struct
import sys
import time
from dataclasses import dataclass
from pathlib import Path

MAGIC = b"U17CAP1\n"


@dataclass(frozen=True)
class Candidate:
    name: str
    description: str
    wire_hex: str | None
    evidence: str
    risk: str


CANDIDATES = {
    "wait-status-query": Candidate(
        "wait-status-query",
        "Read-only host/status query; exact wire bytes unresolved",
        None,
        "U17 wait loop 0x30AA/0x3253 polls FFE1 and consumes FFE3",
        "LOW only after wire bytes and electrical interface are proven; currently unresolved",
    ),
    "state-1": Candidate(
        "state-1",
        "Candidate byte that would enter U17 state 1; packet/prefix unresolved",
        None,
        "0x30C3 -> 0x3109 when internal state A8 is 1",
        "UNKNOWN; do not transmit",
    ),
    "state-2": Candidate(
        "state-2",
        "Candidate byte that would enter U17 state 2; packet/prefix unresolved",
        None,
        "0x30C3 -> 0x3115 when internal state A8 is 2",
        "UNKNOWN; do not transmit",
    ),
}


def parse_baud(value: str) -> float:
    baud = float(value)
    if baud <= 0:
        raise argparse.ArgumentTypeError("baud must be positive")
    return baud


def parse_hex(value: str) -> bytes:
    compact = value.replace(" ", "").replace(":", "").replace("-", "")
    if not compact or len(compact) % 2:
        raise ValueError("hex byte string must contain complete bytes")
    try:
        return bytes.fromhex(compact)
    except ValueError as exc:
        raise ValueError(f"invalid hex byte string: {value!r}") from exc


class CaptureWriter:
    """Timestamped binary records: MAGIC, then ns/u8-direction/u32-len/data."""

    def __init__(self, path: Path):
        self.path = path
        self.handle = path.open("wb")
        self.handle.write(MAGIC)

    def write(self, direction: str, data: bytes, timestamp_ns: int | None = None):
        if direction not in {"RX", "TX"}:
            raise ValueError(direction)
        if not data:
            return
        stamp = time.time_ns() if timestamp_ns is None else timestamp_ns
        direction_byte = 0 if direction == "RX" else 1
        self.handle.write(struct.pack(">QBI", stamp, direction_byte, len(data)))
        self.handle.write(data)
        self.handle.flush()

    def close(self):
        self.handle.close()


def open_serial(device: str, baud: float):
    try:
        import serial  # type: ignore
    except ImportError as exc:
        raise RuntimeError("install pyserial for hardware capture") from exc
    # pyserial accepts float baud rates on platforms exposing arbitrary baud;
    # it raises a platform-specific error if the adapter cannot provide one.
    return serial.Serial(
        port=device,
        baudrate=baud,
        bytesize=serial.EIGHTBITS,
        parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE,
        timeout=0.05,
        write_timeout=1.0,
    )


def capture(device: str, baud: float, duration: float, output: Path):
    serial_port = open_serial(device, baud)
    writer = CaptureWriter(output)
    deadline = time.monotonic() + duration
    try:
        while time.monotonic() < deadline:
            data = serial_port.read(max(1, serial_port.in_waiting or 1))
            if data:
                writer.write("RX", data)
    finally:
        writer.close()
        serial_port.close()


def probe(device: str, baud: float, candidate_name: str, transmit: bool, listen_after: float, output: Path):
    candidate = CANDIDATES[candidate_name]
    if not transmit:
        raise RuntimeError("probe is disabled by default; add --transmit only after wiring/voltage checks")
    if candidate.wire_hex is None:
        raise RuntimeError(f"candidate {candidate.name} has unresolved wire bytes; refusing transmission")
    packet = parse_hex(candidate.wire_hex)
    serial_port = open_serial(device, baud)
    writer = CaptureWriter(output)
    try:
        writer.write("TX", packet)
        serial_port.write(packet)
        serial_port.flush()
        deadline = time.monotonic() + listen_after
        while time.monotonic() < deadline:
            data = serial_port.read(max(1, serial_port.in_waiting or 1))
            if data:
                writer.write("RX", data)
    finally:
        writer.close()
        serial_port.close()


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    sub = root.add_subparsers(dest="mode", required=True)
    cap = sub.add_parser("capture", help="receive-only capture")
    cap.add_argument("--device", required=True)
    cap.add_argument("--baud", required=True, type=parse_baud, help="supports non-standard rates where the adapter/OS does")
    cap.add_argument("--duration", type=float, default=10.0)
    cap.add_argument("--output", type=Path, required=True, help="timestamped binary capture")
    pr = sub.add_parser("probe", help="one-shot probe; refuses unless explicitly enabled")
    pr.add_argument("--device", required=True)
    pr.add_argument("--baud", required=True, type=parse_baud)
    pr.add_argument("--candidate", choices=sorted(CANDIDATES), required=True)
    pr.add_argument("--transmit", action="store_true", help="required explicit transmission opt-in")
    pr.add_argument("--listen-after", type=float, default=1.0)
    pr.add_argument("--output", type=Path, required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.mode == "capture":
            capture(args.device, args.baud, args.duration, args.output)
        else:
            probe(args.device, args.baud, args.candidate, args.transmit, args.listen_after, args.output)
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"u17-host-tool: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
