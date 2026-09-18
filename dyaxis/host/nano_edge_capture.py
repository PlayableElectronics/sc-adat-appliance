#!/usr/bin/env python3
"""Capture and decode passive Arduino-Nano RS-422 edge streams."""
from __future__ import annotations
import argparse, json, math, struct, sys, time
from dataclasses import dataclass
from pathlib import Path

MAGIC = b"DYAXEDG1"
FRAME_HEADER, FRAME_START, FRAME_EDGE = 0xA0, 0xA1, 0xA2
FRAME_OVERFLOW, FRAME_STOP, FRAME_READY = 0xA3, 0xA4, 0xA5

@dataclass
class Capture:
    timer_hz: int
    initial_level: int
    edges: list[tuple[int, int]]
    overflow: int
    stopped: bool
    raw: bytes

def u16(data, pos): return struct.unpack_from("<H", data, pos)[0], pos + 2
def u32(data, pos): return struct.unpack_from("<I", data, pos)[0], pos + 4

def parse_capture(data: bytes) -> Capture:
    # READY may precede the capture header in the USB stream; retain it in the
    # raw file but synchronize parsing at the first capture header.
    header_at = data.find(MAGIC)
    if len(data) < 18 or header_at < 0: raise ValueError("not a DYAXEDG1 capture")
    pos = header_at
    if data[pos + 8] != 1 or data[pos + 9] != FRAME_HEADER: raise ValueError("unsupported capture header")
    timer_hz, pos = u32(data, pos + 10); initial = data[pos]; pos += 2
    _, pos = u16(data, pos)
    edges, tick, overflow, stopped = [], 0, 0, False
    while pos < len(data):
        frame = data[pos]; pos += 1
        if frame == FRAME_START:
            _, pos = u32(data, pos); initial = data[pos]; pos += 1
        elif frame == FRAME_EDGE:
            delta, pos = u32(data, pos)
            if pos >= len(data): raise ValueError("truncated edge record")
            tick += delta; edges.append((tick, data[pos] & 1)); pos += 1
        elif frame == FRAME_OVERFLOW:
            overflow, pos = u32(data, pos); _, pos = u32(data, pos)
        elif frame == FRAME_STOP:
            _, pos = u32(data, pos); overflow, pos = u32(data, pos); stopped = True
        else: raise ValueError(f"unknown frame 0x{frame:02x} at offset {pos - 1}")
    return Capture(timer_hz, initial, edges, overflow, stopped, data)

def level_at(capture: Capture, tick: float, polarity: int = 0) -> int:
    level = capture.initial_level
    for edge_tick, edge_level in capture.edges:
        if edge_tick > tick: break
        level = edge_level
    return level ^ polarity

def estimate_periods(capture: Capture, supplied=None):
    candidates = list(supplied or [])
    # 10416.6667 is a hypothesis only, not a configured or proven baud.
    for baud in (1200, 2400, 4800, 7200, 9600, 10416.6667, 12000, 14400, 19200, 28800, 38400, 57600, 115200):
        candidates.append(capture.timer_hz / baud)
    intervals = [b - a for (a, _), (b, _) in zip(capture.edges, capture.edges[1:]) if b > a]
    if not intervals: return []
    scored = []
    for period in sorted(set(candidates)):
        if period <= 0: continue
        errors = [abs(interval - max(1, round(interval / period)) * period) / period for interval in intervals]
        inliers = sum(error <= 0.18 for error in errors)
        scored.append({"bit_ticks": period, "baud": capture.timer_hz / period,
                       "inlier_fraction": inliers / len(errors),
                       "score": inliers / len(errors) - 0.1 * sum(errors) / len(errors)})
    return sorted(scored, key=lambda item: item["score"], reverse=True)[:12]

def decode_uart(capture, bit_ticks, invert, data_bits, parity, stop_bits):
    if not capture.edges: return {"bytes": [], "attempted": 0, "framing_errors": 0, "parity_errors": 0, "repeatability": 0.0}
    # `invert` normalizes an electrically inverted capture; normalized UART
    # idle is always HIGH and the start bit is LOW.
    idle = 1; active = 0; frames = []; i = 0
    frame_span = (1.5 + data_bits + (0 if parity == "N" else 1) + stop_bits) * bit_ticks
    while i < len(capture.edges):
        tick, level = capture.edges[i]
        previous = capture.initial_level if i == 0 else capture.edges[i - 1][1]
        if (previous ^ int(invert)) != idle or (level ^ int(invert)) != active:
            i += 1
            continue
        value = 0
        for bit in range(data_bits):
            value |= (level_at(capture, tick + (1.5 + bit) * bit_ticks, int(invert)) & 1) << bit
        cursor = tick + (1.5 + data_bits) * bit_ticks; parity_error = False
        if parity != "N":
            sample = level_at(capture, cursor, int(invert)); ones = value.bit_count() + sample
            parity_error = (ones % 2 == 1) if parity == "E" else (ones % 2 == 0); cursor += bit_ticks
        bad_stop = any(level_at(capture, cursor + n * bit_ticks, int(invert)) != idle for n in range(stop_bits))
        frames.append({"tick": tick, "byte": value, "framing_error": bad_stop, "parity_error": parity_error})
        i += 1
        while i < len(capture.edges) and capture.edges[i][0] < tick + frame_span:
            i += 1
    attempted = len(frames); framing = sum(int(f["framing_error"]) for f in frames); parity_errors = sum(int(f["parity_error"]) for f in frames)
    valid = [f for f in frames if not f["framing_error"] and not f["parity_error"]]
    return {"bytes": valid, "attempted": attempted, "framing_errors": framing, "parity_errors": parity_errors,
            "repeatability": len(valid) / attempted if attempted else 0.0, "invert": bool(invert),
            "data_bits": data_bits, "parity": parity, "stop_bits": stop_bits, "bit_ticks": bit_ticks}

def rank_decodes(capture, period_limit=8):
    ranked = []
    for estimate in estimate_periods(capture)[:period_limit]:
        for invert in (False, True):
            for data_bits in (8, 7):
                for parity in ("N", "E", "O"):
                    for stop_bits in (1, 2):
                        result = decode_uart(capture, estimate["bit_ticks"], invert, data_bits, parity, stop_bits)
                        result["baud"] = estimate["baud"]
                        result["score"] = result["repeatability"] * math.log2(result["attempted"] + 1) - 2 * result["framing_errors"] - result["parity_errors"]
                        ranked.append(result)
    return sorted(ranked, key=lambda item: item["score"], reverse=True)

def capture_device(args):
    try: import serial  # type: ignore
    except ImportError as exc: raise RuntimeError("install pyserial for Nano capture") from exc
    with serial.Serial(args.device, args.serial_baud, timeout=0.05) as port:
        port.write(b"R")  # USB control to Nano only; never Dyaxis transmission.
        deadline, raw = time.monotonic() + args.duration, bytearray()
        while time.monotonic() < deadline: raw.extend(port.read(port.in_waiting or 1))
        port.write(b"S"); time.sleep(0.1)
        while port.in_waiting: raw.extend(port.read(port.in_waiting))
    args.output.write_bytes(raw)
    args.timeline.write_text("# Dyaxis passive capture timeline\n\n"
        f"Raw capture: `{args.output}`\n\n"
        "- 00:00:00: begin; keep Dyaxis powered off.\n"
        "- 00:00:00: power on the Dyaxis.\n"
        f"- 00:00:10: press and release `{args.button_name}` once.\n"
        "- 00:00:15: stop capture.\n\n"
        "Observed event notes: _fill in after reviewing the video/capture._\n", encoding="utf-8")

def decode_command(args):
    capture = parse_capture(args.input.read_bytes()); ranked = rank_decodes(capture)
    report = {"timer_hz": capture.timer_hz, "initial_level": capture.initial_level, "edge_count": len(capture.edges),
              "overflow": capture.overflow, "stopped": capture.stopped, "period_estimates": estimate_periods(capture), "ranked_decodes": ranked[:args.top]}
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.bytes_output:
        with args.bytes_output.open("w", encoding="utf-8") as output:
            for frame in ranked[0]["bytes"] if ranked else []:
                output.write(json.dumps({"tick": frame["tick"], "seconds": frame["tick"] / capture.timer_hz,
                                         "byte": frame["byte"], "hex": f"{frame['byte']:02x}"}) + "\n")

def main(argv=None):
    parser = argparse.ArgumentParser(); sub = parser.add_subparsers(dest="command", required=True)
    cap = sub.add_parser("capture"); cap.add_argument("--device", required=True); cap.add_argument("--serial-baud", type=int, default=1000000)
    cap.add_argument("--duration", type=float, default=16.0); cap.add_argument("--button-name", default="named button")
    cap.add_argument("--output", type=Path, required=True); cap.add_argument("--timeline", type=Path, required=True); cap.set_defaults(func=capture_device)
    dec = sub.add_parser("decode"); dec.add_argument("--input", type=Path, required=True); dec.add_argument("--report", type=Path, required=True)
    dec.add_argument("--bytes-output", type=Path); dec.add_argument("--top", type=int, default=10); dec.set_defaults(func=decode_command)
    args = parser.parse_args(argv)
    try: args.func(args)
    except (OSError, ValueError, RuntimeError, struct.error) as exc: parser.error(str(exc))
    return 0

if __name__ == "__main__": sys.exit(main())
