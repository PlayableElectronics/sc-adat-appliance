#!/usr/bin/env python3
"""Generate reproducible U17 architecture reports from reachable disassembly.

This is intentionally evidence-first: it reports valid disassembler boundaries,
literal XDATA/CODE references and explicitly encoded state predicates. It does
not promote unknown external targets or byte coincidences into protocol facts.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path

LABEL_RE = re.compile(r"^(?P<label>[A-Za-z_][A-Za-z0-9_]*):\s*$")
INS_RE = re.compile(r"^\s*(?P<text>[^;]+?)(?:\s*;\s*\[(?P<addr>[0-9A-Fa-f]+)h\])?(?:\s*;.*)?\s*$")
CALL_RE = re.compile(r"\b(?:lcall|acall)\s+(?P<target>[A-Za-z_][A-Za-z0-9_]*)")
JUMP_RE = re.compile(r"\b(?:ljmp|sjmp|ajmp|jz|jnz|jc|jnc|jb|jnb|djnz|cjne)\s+(?P<target>[A-Za-z_][A-Za-z0-9_]*)")
DPTR_RE = re.compile(r"dptr_([0-9A-Fa-f]{4})")
TARGET_RE = re.compile(r"(?:jump|fwd)_([0-9A-Fa-f]{4})")

STATE_ROWS = [
    ("A8=01", "3109", "A2=A5; increment A8", "confirmed local state transition"),
    ("A8=02, A5=01", "3138", "finish phase; clear 017B/A8, or call 32A9 when A2=0", "confirmed local effect"),
    ("A8=02, A5=06", "314B", "require A2 in 01..80; load A6/A7 and enter A8=28", "confirmed transfer setup"),
    ("A8=D8, A5=02", "30EE", "set 017B=1, 017A=32; increment A8", "confirmed local effect"),
    ("A8=28, A5!=FF", "3176/31C1", "decrement A2; compute external-RAM block address", "confirmed download path"),
    ("A8=28, A5=FF", "3176", "terminal transfer handling; may reach 328A", "confirmed transfer terminal"),
    ("A8=2B", "321C", "write A5 to external RAM at 9E:9F", "confirmed external-RAM write"),
    ("A8=63", "3246", "decrement A2; clear 017B/A8 at zero", "confirmed local effect"),
]

def parse_asm(path: Path):
    rows, labels = [], {}
    current = "(unlabeled)"
    for line in path.read_text(errors="replace").splitlines():
        label = LABEL_RE.match(line)
        if label:
            current = label.group("label")
            labels[current] = len(rows)
            continue
        match = INS_RE.match(line)
        if not match:
            continue
        text = match.group("text").strip()
        if not text or text.startswith(("db ", "db\t", "org", ";", "$")):
            continue
        address = int(match.group("addr"), 16) if match.group("addr") else None
        rows.append({"address": address, "text": text, "function": current, "ordinal": len(rows)})
    return rows, labels

def address_text(row):
    if row["address"] is not None:
        return f"0x{row['address']:04X}"
    return f"{row['function']}+{row['ordinal']}"

def target_address(name):
    match = TARGET_RE.fullmatch(name) or re.fullmatch(r"dptr_([0-9A-Fa-f]{4})", name)
    return int(match.group(1), 16) if match else None

def xdata_xrefs(rows):
    out = []
    dptr = None
    function = None
    for row in rows:
        if row["function"] != function:
            function = row["function"]
            dptr = None
        match = DPTR_RE.search(row["text"])
        if match:
            dptr = int(match.group(1), 16)
        if "movx A, @DPTR" in row["text"] and dptr is not None:
            direction = "R"
        elif "movx @DPTR, A" in row["text"] and dptr is not None:
            direction = "W"
        else:
            continue
        out.append((dptr, direction, address_text(row), row["function"], row["text"]))
    return out

def external_calls(rows):
    out = []
    for row in rows:
        match = CALL_RE.search(row["text"])
        if not match:
            continue
        address = target_address(match.group("target"))
        if address is not None and address >= 0x4000:
            out.append((address_text(row), row["function"], f"0x{address:04X}", row["text"]))
    return out

def indirect_rows(rows):
    return [row for row in rows if "@A+DPTR" in row["text"] or "movc" in row["text"]]

def printable_strings(rom: bytes, minimum=4):
    found = []
    start = None
    for index, byte in enumerate(rom + b"\x00"):
        printable = 0x20 <= byte <= 0x7E
        if printable and start is None:
            start = index
        elif not printable and start is not None:
            if index - start >= minimum:
                found.append((start, rom[start:index].decode("ascii", "replace")))
            start = None
    return found

def write_tsv(path, header, rows):
    with path.open("w", encoding="utf-8") as handle:
        handle.write("\t".join(header) + "\n")
        for row in rows:
            handle.write("\t".join(str(value).replace("\t", " ").rstrip() for value in row) + "\n")

def generate(args):
    rows, labels = parse_asm(args.asm)
    xrefs = xdata_xrefs(rows)
    calls = external_calls(rows)
    indirect = indirect_rows(rows)
    strings = printable_strings(args.rom.read_bytes())
    args.out.mkdir(parents=True, exist_ok=True)

    write_tsv(args.out / "u17-xdata-xrefs.tsv", ["address", "direction", "rom_address", "function", "instruction"],
              [(f"0x{a:04X}", d, loc, func, text) for a, d, loc, func, text in xrefs])
    write_tsv(args.out / "u17-external-code-dependencies.tsv", ["rom_address", "caller", "target", "instruction"], calls)
    write_tsv(args.out / "u17-indirect-targets.tsv", ["rom_address", "function", "instruction"],
              [(address_text(row), row["function"], row["text"]) for row in indirect])
    write_tsv(args.out / "u17-string-inventory.tsv", ["rom_address", "text"],
              [(f"0x{address:04X}", text) for address, text in strings])
    write_tsv(args.out / "u17-state-transitions.tsv", ["condition", "code", "effect", "confidence"], STATE_ROWS)

    high = defaultdict(lambda: {"R": 0, "W": 0, "select": 0, "locations": []})
    for address, direction, location, function, text in xrefs:
        if 0xFFE0 <= address <= 0xFFFF:
            high[address][direction] += 1
            high[address]["locations"].append(f"{location} {function}: {text}")
    code_labels = [name for name in labels if name.startswith(("jump_", "fwd_")) or name in ("RESET_TARGET", "SERIAL_ISR")]
    classification = {
        "method": "disasm51 reachable instruction boundaries plus literal ROM/XDATA analysis",
        "instruction_count": len(rows),
        "labeled_regions": len(code_labels),
        "external_code_call_count": len(calls),
        "indirect_reference_count": len(indirect),
        "literal_high_xdata": {
            f"0x{address:04X}": value for address, value in sorted(high.items())
        },
        "limits": [
            "External CODE bodies are outside the U17 image.",
            "Indirect dispatch tables are reported but not assigned without bus evidence.",
            "String references through external FE06 services are not recoverable from U17 alone.",
        ],
    }
    (args.out / "u17-code-classification.json").write_text(json.dumps(classification, indent=2) + "\n", encoding="utf-8")

    (args.out / "U17_COMPLETE_PROGRAM_MAP.md").write_text(f"""# U17 complete reachable program map

Generated from `{args.asm.name}` and the verified tracked ROM. The map covers
**{len(rows)} valid instruction records** across **{len(labels)} labeled regions**;
it is a complete reachable-vector map, not a claim that unreachable ROM bytes
are non-code. External CODE calls remain unresolved dependencies.

## Address-space boundaries

- CODE: U17 physical ROM `0x0000..0x7FFF`; external CODE targets are listed in
  `u17-external-code-dependencies.tsv`.
- Internal RAM/SFR: P80C552 direct/register operations at valid instruction
  boundaries only.
- XDATA: literal DPTR references are listed in `u17-xdata-xrefs.tsv`; external
  RAM/program window and service windows are not conflated.

## Confirmed entry families

- Reset/startup: `0x0000 -> 0x2F6F -> 0x2FD2 -> 0x01E0`.
- Local checks/services: `0x037C`, `0x03A4`, `0x032F`, `0x034D`, `0x1440`.
- Main service state machine: `0x30A7..0x328A`.
- Interrupt shims: `0x33F8`, `0x3416`, `0x3434`, `0x3452`, `0x3470`,
  `0x348E`, `0x34AC..0x357E`.

Indirect/table references are preserved in `u17-indirect-targets.tsv`; no
indirect target is silently promoted to a protocol or peripheral assignment.
""", encoding="utf-8")

    (args.out / "U17_STARTUP_STATE_MACHINE.md").write_text("""# U17 startup state machine

```text
0000 -> 2F6F: clear internal RAM; clear XDATA 0000..7FFF and FE00..FEFF
2FD2: apply ROM table 2211 initialization; enter 01E0
01E0: disable interrupts; external services; FFF1/FFF0 status test
      FEEE/FEEF setup; Timer-2/capture setup; enable EA
      FE06 boot/checksum/master-reset messages; validate RAM/signature
30A7: initialize candidate peripheral/service window through 3348
30AA: wait on FFE1.0; consume FFE3; dispatch state A8
3253: timeout/status handling; return to 30AA
328A: disable services and launch external code at 8000, or reset path
```

The exact host-wait interpretation remains unresolved. `FFE1/FFE3` is a
candidate FPGA/peripheral service-register window, possibly decoded or
controlled by PAL logic; it is not proven to be Macintosh wire traffic.

Accepted state-dependent values and effects are in
`u17-state-transitions.tsv`.
""", encoding="utf-8")

    (args.out / "U17_EXTERNAL_CODE_DEPENDENCIES.md").write_text(f"""# U17 external CODE dependencies

The reachable U17 image makes **{len(calls)}** literal external CODE call
references. The full caller/target table is `u17-external-code-dependencies.tsv`.

The repeated `0xFE00..0xFE6F` calls and `0xFEC1..0xFEF9` interrupt-service
targets are outside the 32 KiB EPROM. Static evidence cannot distinguish
mirrored ROM, FPGA/peripheral-provided bus behavior, external RAM overlays,
or another socketed ROM. The two undumped socketed ROM candidates remain
possible contributors, but no target-to-socket mapping is proven.

`LCALL 0x8000` is a distinct external-code launch after the U17 transfer and
validation path; it is not evidence that the external CODE service calls are
ordinary registers.
""", encoding="utf-8")

    (args.out / "U17_SERVICE_WINDOW.md").write_text("""# U17 FFE1/FFE3 service-window analysis

`FFE1` is read at `30AA` and `3253`, and written by `3332` and `3348`.
`FFE3` is read by `30C3` and written by `327E`. The complete literal xref list
is `u17-xdata-xrefs.tsv`.

The strongest conservative interpretation is a candidate FPGA/peripheral
service-register window, possibly decoded or controlled by PAL logic. The ROM
does not prove that the PAL owns it, that it is a mailbox to a processor, or
that it is the Macintosh protocol.

The service values `01`, `02`, `06` and `FF` have state-dependent effects in
the generated state table. Values `06` and `FF` enter the external-RAM transfer
path and are not safe candidates for active control testing.
""", encoding="utf-8")

    (args.out / "U17_SERIAL_AND_HOST_PROTOCOL.md").write_text("""# U17 serial and host-protocol boundary

The SIO0 vector at `0023` reaches `3416`. That ISR reads XDATA `FED0`, loads
PSW from the returned byte, calls external CODE `FED1`, restores context and
returns `RETI`. Related interrupt shims use `FEC0/FEC4/FEC8/FECC/FED8..FEF8`
and adjacent external CODE targets.

U17 contains no reachable direct S0CON/S0BUF/TH1/TMOD setup in this pass.
Therefore framing, buffers, escape bytes, lengths, checksums, command IDs,
Z85230 channel selection and baud remain unproven. Passive capture or an
external-bus trace is required; the local FFE1/FFE3 service window must not be
used as a wire-protocol substitute.
""", encoding="utf-8")

    (args.out / "U17_STANDALONE_CAPABILITIES.md").write_text("""# U17 standalone capabilities

Confirmed U17-local behavior includes reset/startup sequencing, external RAM
clear/checksum/signature validation, boot/checksum/master-reset message
selection through FE06 services, peripheral/service initialization, timeout
handling, external-RAM transfer and an external-code launch at `0x8000`.

Standalone fader, LED and display activity is confirmed at the console level,
but this U17 ROM alone does not contain a statically proven complete fader/LED
driver loop. The XC3030 probably implements scanning/interface logic and the
PAL likely supplies glue/decode/control logic; exact assignments remain partly
inferential. Two socketed ROM candidates and external CODE services mean U17
is not yet proven to contain the entire executable system.
""", encoding="utf-8")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("asm", type=Path)
    parser.add_argument("rom", type=Path)
    parser.add_argument("out", type=Path)
    generate(parser.parse_args())

if __name__ == "__main__":
    main()
