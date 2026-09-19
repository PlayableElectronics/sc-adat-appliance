#!/usr/bin/env python3
"""Bounded U17 execution harness using Debian SDCC/uCsim's 8051 core.

uCsim supplies instruction execution. This integration layer supplies a 64 KiB
CODE image, an independent XRAM fixture, terminal breakpoints, and compact
experiment summaries. It intentionally does not emulate FPGA/PAL/Z85230
behavior or claim that a reproduced path proves physical wiring.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import tempfile
from pathlib import Path

SIZE = 0x8000
U17 = Path("dyaxis/firmware/original/41.005.415.Z1-U17-V1.06-AM27C256.bin")
ORIGINAL = Path("dyaxis/firmware/original/41.005.415.Z1-U17-DS1230Y-100.bin")
CANDIDATE = Path("dyaxis/firmware/candidates/41.005.415.Z1-U17-first-app-SJMP-8000.bin")
BREAKS = {0x2F6F: "reset-entry", 0x02FD: "Checksum Good", 0x0311: "Checksum Failed", 0x30A7: "marker-wait", 0x328A: "launch-prelude", 0x8000: "application-entry"}


def read_image(path: Path) -> bytes:
    data = path.read_bytes()
    if len(data) != SIZE:
        raise ValueError(f"{path}: expected {SIZE} bytes, got {len(data)}")
    return data


def ihex(data: bytes) -> str:
    lines = []
    for address in range(0, len(data), 16):
        chunk = data[address:address + 16]
        record = bytes((len(chunk), (address >> 8) & 0xFF, address & 0xFF, 0)) + chunk
        lines.append(":" + record.hex().upper() + f"{(-sum(record)) & 0xFF:02X}")
    return "\n".join(lines + [":00000001FF"]) + "\n"


def xram_commands(image: bytes) -> list[str]:
    return [
        "set memory XRAM 0x%04X %s" % (0x8000 + offset, " ".join(f"{value:02X}" for value in image[offset:offset + 16]))
        for offset in range(0, SIZE, 16)
    ]


def checksum_summary(image: bytes) -> dict[str, object]:
    values = image[:0x7DFD]
    total = sum(values) & 0xFFFF
    complement = (~total) & 0xFFFF
    return {
        "start_cpu": "0x8000",
        "end_exclusive_cpu": "0xFDFD",
        "read_count": len(values),
        "sum_r4_r5": f"0x{total:04X}",
        "complement_r6_r7": f"0x{complement:04X}",
        "supplied_fdfc_fdff": image[0x7DFC:0x7E00].hex().upper(),
    }


def projected_path(image: bytes) -> str:
    """Independent path projection used when uCsim is held in a service loop."""
    if image[0x7DFE:0x7E00] == b"\xAA\x55" and image[0x7DFC:0x7DFE] == b"\xAA\x55":
        return "marker-wait"
    total = sum(image[:0x7DFD]) & 0xFFFF
    if image[0x7DFE:0x7E00] == ((~total) & 0xFFFF).to_bytes(2, "big"):
        return "Checksum Good"
    return "Checksum Failed"


def mapping_image(name: str, original: bytes, candidate: bytes) -> tuple[bytes, str]:
    if name == "original":
        return original, "original DS1230 dump"
    if name == "candidate":
        return candidate, "candidate de42ce8"
    if name == "zero":
        return bytes(SIZE), "independent zeroed U18-style SRAM fixture"
    if name == "ff":
        return bytes([0xFF]) * SIZE, "unmapped XDATA diagnostic default 0xFF"
    if name == "mutable-original":
        return bytearray(original), "mutable U18-style RAM initialized from original DS1230"
    raise ValueError(f"unknown image mapping {name}")


def run_one(ucsim: str, code_name: str, xdata_name: str, root: Path, keep_trace: Path | None = None) -> dict[str, object]:
    u17 = read_image(root / U17)
    original = read_image(root / ORIGINAL)
    candidate = read_image(root / CANDIDATE)
    external_code, code_description = mapping_image(code_name, original, candidate)
    xdata, xdata_description = mapping_image(xdata_name, original, candidate)
    with tempfile.TemporaryDirectory(prefix="u17-ucsim-") as directory:
        work = Path(directory)
        (work / "code.hex").write_text(ihex(u17 + bytes(external_code)), encoding="ascii")
        commands = ['file "code.hex"'] + xram_commands(bytes(xdata))
        commands.extend(f"break 0x{address:04X}" for address in BREAKS)
        # -g does not reliably start after a -C command file in all uCsim
        # builds; an explicit bounded run followed by quit is deterministic.
        commands.extend(("run", "quit"))
        (work / "commands").write_text("\n".join(commands) + "\n", encoding="ascii")
        try:
            completed = subprocess.run(
                [ucsim, "-q", "-C", "commands"],
                cwd=work,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=5,
                check=False,
            )
            trace = completed.stdout
            timed_out = False
            returncode = completed.returncode
        except subprocess.TimeoutExpired as exc:
            trace = (exc.stdout or "")
            if isinstance(trace, bytes):
                trace = trace.decode(errors="replace")
            timed_out = True
            returncode = None
        if keep_trace:
            keep_trace.parent.mkdir(parents=True, exist_ok=True)
            keep_trace.write_text(trace, encoding="utf-8")
    fetches = [int(value, 16) for value in re.findall(r"0x([0-9a-fA-F]{6})\s+F\?", trace)]
    hit = re.search(r"0x([0-9a-fA-F]{6})\s+F\?", trace)
    pc = int(hit.group(1), 16) if hit else None
    final_path = BREAKS.get(pc, "bounded-stop/no terminal breakpoint")
    supplied = bytes(xdata)
    result = {
        "core": "SDCC uCsim 0.8.15 (Debian sdcc-ucsim 4.5.0+dfsg-1)",
        "code_mapping": code_name,
        "code_description": code_description,
        "xdata_mapping": xdata_name,
        "xdata_description": xdata_description,
        "executed_instruction_count": "not exposed by uCsim batch breakpoint output",
        "stop_reason": f"terminal breakpoint 0x{pc:04X}" if pc is not None else ("uCsim timeout in startup/service path" if timed_out else f"uCsim exit {returncode}"),
        "display_strings": [final_path] if final_path in {"Checksum Good", "Checksum Failed", "marker-wait"} else [],
        "checksum": checksum_summary(supplied),
        "comparison_addresses": ["0x02EB low byte", "0x02F0 high byte"],
        "final_path": final_path,
        "static_path_projection": projected_path(supplied),
        "execution_status": "terminal breakpoint observed" if pc is not None else "uCsim did not reach a terminal breakpoint; projection is not instruction-execution evidence",
        "reached_0x328A": pc in {0x328A, 0x8000},
        "lcall_0x8000_observed": pc == 0x8000,
        "code_0x8000_fetched": pc == 0x8000,
        "unknown_peripheral_accesses": "uCsim default P80C552 SFR/XDATA behavior; no FPGA/PAL/Z85230 success is invented",
        "trace_sha256": hashlib.sha256(trace.encode()).hexdigest(),
        "bounded_trace_excerpt": trace.splitlines()[-12:],
        "breakpoint_fetches": [f"0x{address:04X}" for address in fetches if address in BREAKS],
    }
    return result


EXPERIMENTS = {
    "A": ("original", "original"),
    "B": ("candidate", "candidate"),
    "C": ("candidate", "zero"),
    "D": ("candidate", "mutable-original"),
    "E-original-code-candidate-xdata": ("original", "candidate"),
    "E-candidate-code-original-xdata": ("candidate", "original"),
    "E-original-both": ("original", "original"),
    "E-candidate-both": ("candidate", "candidate"),
    "F": ("candidate", "zero"),
    "G-zero-default": ("candidate", "zero"),
    "G-ff-default": ("candidate", "ff"),
    "H-fe-code-ds1230-xdata-u18": ("candidate", "zero"),
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ucsim", required=True)
    parser.add_argument("--root", type=Path, default=Path("/work"))
    parser.add_argument("--experiment", choices=["all", *EXPERIMENTS], default="all")
    parser.add_argument("--trace-dir", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    selected = EXPERIMENTS if args.experiment == "all" else {args.experiment: EXPERIMENTS[args.experiment]}
    results = []
    for name, (code, xdata) in selected.items():
        trace = args.trace_dir / f"{name}.log" if args.trace_dir else None
        result = run_one(args.ucsim, code, xdata, args.root, trace)
        result["experiment"] = name
        results.append(result)
    payload = {"experiments": results, "safety": "read-only software emulation; no hardware access or serial transmission"}
    text = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
