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


def read_capture(path: Path):
    """Read U17CAP1 records without interpreting them as protocol frames."""
    data = path.read_bytes()
    if not data.startswith(MAGIC):
        raise ValueError("not a U17CAP1 capture")
    records = []
    offset = len(MAGIC)
    header_size = struct.calcsize(">QBI")
    while offset < len(data):
        if len(data) - offset < header_size:
            raise ValueError("truncated capture record header")
        timestamp, direction, length = struct.unpack_from(">QBI", data, offset)
        offset += header_size
        if direction not in (0, 1) or offset + length > len(data):
            raise ValueError("invalid capture record")
        records.append({"timestamp_ns": timestamp, "direction": "RX" if direction == 0 else "TX",
                        "data": data[offset:offset + length]})
        offset += length
    return records


def simulate_service_byte(state: int, value: int, count: int = 0):
    """Apply the ROM's FFE3/A8 dispatch to one candidate byte.

    This is explicitly not a wire parser: each observed RX byte is treated as
    a hypothetical service byte solely to expose state-machine correlations.
    """
    before = state
    action = "ignored/default -> 3253"
    after = state
    next_count = count
    if state == 0 and value == 0x02:
        action, after = "arm 017B/017A; advance", 1
    elif state == 1:
        action, after, next_count = "store A2=A5; advance", 2, value
    elif state == 2 and value == 0x01:
        action, after = ("call 32A9 then clear" if next_count == 0 else "clear active state"), 0
    elif state == 2 and value == 0x06:
        if 1 <= next_count <= 0x80:
            action, after = "accept count; prepare transfer", 0x28
        else:
            action, after = "reject count; clear active state", 0
    elif state == 0x28:
        next_count = (next_count - 1) & 0xFF
        if value == 0xFF:
            action, after = ("terminal; launch path" if next_count == 0 else "terminal with bytes remaining; error state"), 0 if next_count == 0 else 0x5A
        elif value < 0xFC:
            action, after = f"select block {value:02X}; advance to payload state", 0x29
        else:
            action, after = "reject block index; error state", 0x5A
    elif state == 0x29:
        next_count = (next_count - 1) & 0xFF
        action, after = ("write payload byte; transfer complete" if next_count == 0 else "write payload byte; continue"), 0 if next_count == 0 else 0x29
    elif state == 0x5A:
        next_count = (next_count - 1) & 0xFF
        action, after = ("cleanup complete" if next_count == 0 else "decrement cleanup counter"), 0 if next_count == 0 else 0x5A
    return {"before_state": f"0x{before:02X}", "service_byte": value,
            "action": action, "after_state": f"0x{after:02X}", "count": next_count}, after, next_count


def decode_capture(path: Path):
    records = read_capture(path)
    events, state, count = [], 0, 0
    rx_bytes = []
    for record in records:
        if record["direction"] != "RX":
            continue
        for index, value in enumerate(record["data"]):
            rx_bytes.append({"timestamp_ns": record["timestamp_ns"], "byte": value})
            event, state, count = simulate_service_byte(state, value, count)
            event.update(timestamp_ns=record["timestamp_ns"], byte_index=index)
            events.append(event)
    return {"format": "U17CAP1", "record_count": len(records), "rx_byte_count": len(rx_bytes),
            "records": [{"timestamp_ns": x["timestamp_ns"], "direction": x["direction"],
                         "length": len(x["data"]), "hex": x["data"].hex()} for x in records],
            "rx_bytes": [{**x, "hex": f"{x['byte']:02x}"} for x in rx_bytes],
            "candidate_service_state_events": events,
            "interpretation": "RX bytes are not proven FFE3 service bytes; no wire framing or packet semantics are inferred."}


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
    dec = sub.add_parser("decode", help="decode-only raw capture/state correlation; never transmits")
    dec.add_argument("--input", type=Path, required=True)
    dec.add_argument("--output", type=Path, required=True)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.mode == "capture":
            capture(args.device, args.baud, args.duration, args.output)
        elif args.mode == "probe":
            probe(args.device, args.baud, args.candidate, args.transmit, args.listen_after, args.output)
        else:
            args.output.write_text(json.dumps(decode_capture(args.input), indent=2) + "\n", encoding="utf-8")
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"u17-host-tool: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
