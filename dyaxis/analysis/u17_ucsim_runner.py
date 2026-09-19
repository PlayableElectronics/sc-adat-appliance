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
import os
import pty
import re
import select
import signal
import tempfile
import time
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


BREAKPOINT_STOP_RE = re.compile(r"Stop at 0x([0-9A-Fa-f]+):\s*\([0-9]+\) Breakpoint")
TICKS_RE = re.compile(r"stepped ([0-9]+) ticks")
STATE_PC_RE = re.compile(r"CPU state=.*?PC=\s*0x([0-9A-Fa-f]+)")
INST_RE = re.compile(r"Inst=\s*([0-9]+)")
ACC_RE = re.compile(r"ACC=\s*0x([0-9A-Fa-f]+)")
REG_ROW_RE = re.compile(r"\s+([0-9A-Fa-f]{2}(?:\s+[0-9A-Fa-f]{2}){7})\s*$", re.MULTILINE)
DPTR_RE = re.compile(r"DPTR=\s*0x([0-9A-Fa-f]+)")
SP_RE = re.compile(r"SP\s+0x([0-9A-Fa-f]+)")


def ucsim_session(ucsim: str, work: Path, commands: list[str], instruction_limit: int = 200_000) -> dict[str, object]:
    """Run uCsim through a PTY and require an explicit Stop-at event.

    A pipe can leave uCsim's console waiting for terminal input. The PTY is
    intentional: it makes `step`, `state`, and `quit` follow the documented
    interactive console. The execution request is a bounded instruction step,
    not an unbounded `run`; the short wall-clock guard only protects the test
    process if the console itself fails to respond.
    """
    command_file = work / "commands"
    command_file.write_text("\n".join(commands) + "\n", encoding="ascii")
    pid, fd = pty.fork()
    if pid == 0:
        os.chdir(work)
        os.execv(ucsim, [ucsim, "-q", "-C", "commands"])
    output = bytearray()
    deadline = time.monotonic() + 5
    expected_breakpoints = sum(command.startswith("break ") for command in commands)
    # Wait until the -C file has installed its breakpoints. Sending `run`
    # immediately races uCsim startup and is silently consumed before the
    # command file has finished, which was the original false-timeout bug.
    while time.monotonic() < deadline and len(output) < 2_000_000:
        ready, _, _ = select.select([fd], [], [], 0.1)
        if not ready:
            continue
        try:
            chunk = os.read(fd, 8192)
        except OSError:
            break
        if not chunk:
            break
        output.extend(chunk)
        if output.decode(errors="replace").count("Breakpoint ") >= expected_breakpoints:
            break
    os.write(fd, f"step {instruction_limit}\n".encode("ascii"))
    stop = None
    while time.monotonic() < deadline and len(output) < 2_000_000:
        ready, _, _ = select.select([fd], [], [], 0.1)
        if not ready:
            continue
        try:
            chunk = os.read(fd, 8192)
        except OSError:
            break
        if not chunk:
            break
        output.extend(chunk)
        text = output.decode(errors="replace")
        # A bounded `step N` also prints “Stop at ...: (...) stepped ...”.
        # Only the explicit Breakpoint event is evidence of a requested
        # address being executed.
        matches = list(BREAKPOINT_STOP_RE.finditer(text))
        if matches:
            stop = matches[-1]
            break
    # Query state after both a breakpoint stop and a bounded-step stop. This
    # is the authoritative fallback when no breakpoint event was emitted.
    os.write(fd, b"state\nquit\n")
    time.sleep(0.05)
    drain_deadline = time.monotonic() + 1
    while time.monotonic() < drain_deadline:
        ready, _, _ = select.select([fd], [], [], 0.1)
        if not ready:
            break
        try:
            chunk = os.read(fd, 8192)
        except OSError:
            break
        if not chunk:
            break
        output.extend(chunk)
    try:
        os.close(fd)
    except OSError:
        pass
    # A bounded `step` can leave the console child alive after it has printed
    # its state. Never block indefinitely in waitpid: terminate only this
    # child if it has not exited promptly.
    status = None
    for _ in range(10):
        try:
            waited, status = os.waitpid(pid, os.WNOHANG)
        except ChildProcessError:
            break
        if waited:
            break
        time.sleep(0.05)
    else:
        try:
            os.kill(pid, signal.SIGTERM)
            _, status = os.waitpid(pid, 0)
        except (ChildProcessError, ProcessLookupError):
            pass
    returncode = os.waitstatus_to_exitcode(status) if status is not None else None
    text = output.decode(errors="replace")
    pc = int(stop.group(1), 16) if stop else None
    ticks_match = TICKS_RE.search(text)
    ticks = int(ticks_match.group(1)) if ticks_match else None
    inst_match = INST_RE.search(text)
    instructions = int(inst_match.group(1)) if inst_match else None
    state_match = STATE_PC_RE.search(text)
    state_pc = int(state_match.group(1), 16) if state_match else None
    acc_match = ACC_RE.search(text)
    dptr_match = DPTR_RE.search(text)
    sp_match = SP_RE.search(text)
    reg_match = REG_ROW_RE.search(text)
    registers = None
    if reg_match:
        registers = dict(zip((f"R{i}" for i in range(8)),
                             [f"0x{value.upper()}" for value in reg_match.group(1).split()]))
    if acc_match:
        registers = registers or {}
        registers["ACC"] = f"0x{acc_match.group(1).upper()}"
    if dptr_match:
        registers = registers or {}
        registers["DPTR"] = f"0x{dptr_match.group(1).upper()}"
    if sp_match:
        registers = registers or {}
        registers["SP"] = f"0x{sp_match.group(1).upper()}"
    if ticks is not None and ticks > instruction_limit * 24:
        raise RuntimeError("uCsim exceeded deterministic instruction limit")
    return {
        "stop_pc": f"0x{pc:04X}" if pc is not None else None,
        "state_pc": f"0x{state_pc:04X}" if state_pc is not None else None,
        "executed_ticks": ticks,
        "instruction_count": instructions,
        "registers": registers,
        "stop_event": bool(stop),
        "returncode": returncode,
        "output": text,
    }


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
        (work / "commands").write_text("\n".join(commands) + "\n", encoding="ascii")
        session = ucsim_session(ucsim, work, commands)
        trace = session["output"]
        timed_out = not session["stop_event"]
        returncode = session["returncode"]
        if keep_trace:
            keep_trace.parent.mkdir(parents=True, exist_ok=True)
            keep_trace.write_text(trace, encoding="utf-8")
    fetches = [int(value, 16) for value in re.findall(
        r"Stop at 0x([0-9a-fA-F]+):\s*\([0-9]+\) Breakpoint", trace)]
    pc = int(session["stop_pc"], 16) if session["stop_pc"] else None
    final_path = BREAKS.get(pc, "bounded-stop/no terminal breakpoint")
    supplied = bytes(xdata)
    result = {
        "core": "SDCC uCsim 0.8.15 (Debian sdcc-ucsim 4.5.0+dfsg-1)",
        "code_mapping": code_name,
        "code_description": code_description,
        "xdata_mapping": xdata_name,
        "xdata_description": xdata_description,
        "executed_instruction_count": session["instruction_count"],
        "stop_reason": f"explicit Stop-at event 0x{pc:04X}" if pc is not None else (f"bounded step ended at {session['state_pc']} without terminal breakpoint" if session["state_pc"] else ("bounded step produced no state" if timed_out else f"uCsim exit {returncode}")),
        "display_strings": [final_path] if final_path in {"Checksum Good", "Checksum Failed", "marker-wait"} else [],
        "checksum": checksum_summary(supplied),
        "comparison_addresses": ["0x02EB low byte", "0x02F0 high byte"],
        "final_path": final_path,
        "static_path_projection": projected_path(supplied),
        "execution_status": "terminal breakpoint observed" if pc is not None else "bounded instruction execution completed without a terminal breakpoint; projection is not instruction-execution evidence",
        "uCsim_state_pc": session["state_pc"],
        "uCsim_executed_ticks": session["executed_ticks"],
        "final_registers": session["registers"],
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
    "G-ff-default": ("candidate", "ff"),
}


def synthetic_smoke(ucsim: str, root: Path) -> dict[str, object]:
    """Known reset -> MOV A,#42 -> terminating SJMP fixture."""
    fixture = root / "dyaxis/analysis/fixtures/u17-ucsim-smoke.hex"
    with tempfile.TemporaryDirectory(prefix="u17-ucsim-smoke-") as directory:
        work = Path(directory)
        (work / "code.hex").write_text(fixture.read_text(encoding="ascii"), encoding="ascii")
        session = ucsim_session(ucsim, work, ['file "code.hex"', "break 0x0005"])
    return {
        "fixture": "reset LJMP 0003; MOV A,#42; SJMP $ at 0005",
        "expected_stop_pc": "0x0005",
        "expected_accumulator": "0x42",
        "actual_stop_pc": session["stop_pc"],
        "actual_state_pc": session["state_pc"],
        "actual_accumulator": (f"0x{int(ACC_RE.search(session['output']).group(1), 16):02X}"
                                if ACC_RE.search(session["output"]) else None),
        "instruction_count": session["instruction_count"],
        "stop_event": session["stop_event"],
        "executed_ticks": session["executed_ticks"],
        "output_excerpt": session["output"].splitlines()[-12:],
    }


def validation_probe(ucsim: str, root: Path, address: int) -> dict[str, object]:
    """Probe one startup/checksum boundary with candidate CODE and XDATA.

    Each probe resets the CPU and has one explicit breakpoint. This is a
    bounded observation aid, not a peripheral or bus emulator.
    """
    u17 = read_image(root / U17)
    candidate = read_image(root / CANDIDATE)
    with tempfile.TemporaryDirectory(prefix="u17-validation-") as directory:
        work = Path(directory)
        (work / "code.hex").write_text(ihex(u17 + candidate), encoding="ascii")
        commands = ['file "code.hex"'] + xram_commands(candidate) + [f"break 0x{address:04X}"]
        session = ucsim_session(ucsim, work, commands)
    text = session["output"]
    return {
        "breakpoint": f"0x{address:04X}",
        "stop_event": session["stop_event"],
        "stop_pc": session["stop_pc"],
        "state_pc": session["state_pc"],
        "instruction_count": session["instruction_count"],
        "registers": session["registers"],
        "trace_excerpt": text.splitlines()[-22:],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ucsim", required=True)
    parser.add_argument("--root", type=Path, default=Path("/work"))
    parser.add_argument("--experiment", choices=["all", *EXPERIMENTS], default="all")
    parser.add_argument("--trace-dir", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--smoke", action="store_true")
    parser.add_argument("--validation", action="store_true")
    args = parser.parse_args()
    if args.smoke:
        print(json.dumps(synthetic_smoke(args.ucsim, args.root), indent=2) + "\n")
        return
    if args.validation:
        addresses = [0x0293, 0x0296, 0x0299, 0x02CD, 0x02E8, 0x02EB,
                     0x02F0, 0x02FD, 0x0311]
        print(json.dumps({"mapping": "candidate CODE + candidate XDATA",
                          "probes": [validation_probe(args.ucsim, args.root, address)
                                     for address in addresses]}, indent=2) + "\n")
        return
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
