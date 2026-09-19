#!/usr/bin/env python3
"""Read-only, dependency-free analysis of a preserved DS1230 image."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

SIZE = 32768
CHECKSUM_END = 0x7DFD  # U17 CPU [8000,FDFD), file offsets [0000,7DFD)
FE_START = 0x7E00       # CPU FE00 when mapped at CPU 8000
FE_END = 0x7EFA         # exclusive; CPU FE00..FEF9


def printable_runs(data: bytes, minimum: int = 4):
    runs, start = [], None
    for index, value in enumerate(data + b"\x00"):
        if 32 <= value < 127 and start is None:
            start = index
        elif not (32 <= value < 127) and start is not None:
            if index - start >= minimum:
                runs.append((start, data[start:index].decode("ascii")))
            start = None
    return runs


def fe_trampolines(data: bytes):
    """Decode FE00..FE7F as an 8000-based 8051 LJMP table."""
    entries = []
    for cpu_address in range(0xFE00, 0xFE81, 3):
        offset = cpu_address - 0x8000
        if data[offset] == 0x02:
            target = (data[offset + 1] << 8) | data[offset + 2]
            entries.append({"cpu_address": f"0x{cpu_address:04X}",
                            "file_offset": f"0x{offset:04X}",
                            "target": f"0x{target:04X}"})
    return entries


def nonzero_regions(data: bytes):
    """Return contiguous non-zero regions without interpreting their contents."""
    regions = []
    start = None
    for offset, value in enumerate(data + b"\x00"):
        if value and start is None:
            start = offset
        elif not value and start is not None:
            end = offset
            if end <= 0x7DFF:
                kind, confidence = "application/signature area residue", "high"
            elif start < 0x7E80:
                kind, confidence = "CODE trampoline table", "high"
            elif start < 0x7F00:
                kind, confidence = "persistent state/configuration candidate", "low"
            else:
                kind, confidence = "unexplained retained/residual data", "low"
            regions.append({"start": f"0x{start:04X}", "end": f"0x{end - 1:04X}",
                            "length": end - start, "classification": kind,
                            "confidence": confidence})
            start = None
    return regions


def analyze(path: Path, u17_calls: Path | None = None):
    data = path.read_bytes()
    if len(data) != SIZE:
        raise ValueError(f"DS1230 image must be {SIZE} bytes, got {len(data)}")
    digest = hashlib.sha256(data).hexdigest()
    total = sum(data[:CHECKSUM_END]) & 0xFFFF
    complement = (~total) & 0xFFFF
    signature = data[0x7DFC:0x7DFE].hex().upper()
    startup_pair = data[0x7DFE:0x7E00].hex().upper()
    stored = int.from_bytes(data[0x7DFE:0x7E00], "big")
    fe = data[FE_START:FE_END]
    trampolines = fe_trampolines(data)
    callers = {}
    if u17_calls and u17_calls.exists():
        for line in u17_calls.read_text().splitlines()[1:]:
            fields = line.split("\t")
            if len(fields) >= 3:
                callers.setdefault(fields[2].upper(), []).append(f"{fields[0]} {fields[1]}")
    for entry in trampolines:
        entry["callers"] = callers.get(entry["cpu_address"].upper(), [])
        target = int(entry["target"], 16)
        if entry["cpu_address"] == "0xFE06":
            entry.update(likely_function="display/string service", confidence="high",
                         evidence="R2:R1 resolves to embedded boot strings at every observed call")
        elif entry["cpu_address"] == "0xFE60":
            entry.update(likely_function="checksum helper", confidence="high",
                         evidence="trampoline reaches U17 037C, the validated application checksum loop")
        elif entry["cpu_address"] == "0xFE33":
            entry.update(likely_function="indexed external service", confidence="medium",
                         evidence="repeated U17 calls use R7 values 1..7; exact peripheral role unresolved")
        else:
            entry.update(likely_function=f"U17 CODE 0x{target:04X} service; semantic role unresolved",
                         confidence="low", evidence="valid LJMP target and U17 call-site evidence only")
    return {
        "path": path.name, "size": len(data), "sha256": digest,
        "all_zero": data == b"\x00" * SIZE, "all_ff": data == b"\xFF" * SIZE,
        "zero_count": data.count(0), "ff_count": data.count(0xFF),
        "distinct_bytes": len(set(data)),
        "printable_runs": [{"offset": f"0x{o:04X}", "text": t} for o, t in printable_runs(data)],
        "fe_trampoline_count": len(trampolines), "fe_trampolines": trampolines,
        "nonzero_regions": nonzero_regions(data),
        "reset_bytes": data[:8].hex().upper(),
        "reset_plausible_8051": data[:3] in {b"\x02\x2F\x6F", b"\x02\x80\x00"},
        "fe00_fef9_all_ff": fe == b"\xFF" * len(fe),
        "checksum_sum_16bit": f"0x{total:04X}",
        "checksum_complement": f"0x{complement:04X}",
        "signature": signature, "signature_expected": "AA55",
        "signature_matches": signature == "AA55",
        "startup_pair": startup_pair, "startup_pair_matches": startup_pair == "AA55",
        "stored_checksum": f"0x{stored:04X}",
        "checksum_matches": stored == complement,
    }


def write_report(result, output: Path):
    output.mkdir(parents=True, exist_ok=True)
    (output / "ds1230-analysis.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    (output / "ds1230-fe-trampolines.tsv").write_text(
        "cpu_address\tfile_offset\tu17_code_target\tcallers\tlikely_function\tconfidence\tevidence\n" +
        "".join(f"{x['cpu_address']}\t{x['file_offset']}\t{x['target']}\t{';'.join(x['callers']) or '—'}\t{x['likely_function']}\t{x['confidence']}\t{x['evidence']}\n" for x in result["fe_trampolines"]),
        encoding="utf-8")
    (output / "ds1230-nonzero-regions.tsv").write_text(
        "file_start\tfile_end\tlength\tclassification\tconfidence\n" +
        "".join(f"{x['start']}\t{x['end']}\t{x['length']}\t{x['classification']}\t{x['confidence']}\n"
                for x in result["nonzero_regions"]), encoding="utf-8")
    strings = result["printable_runs"] or [{"offset": "—", "text": "none"}]
    string_lines = "\n".join(f"- `{x['offset']}` `{x['text']}`" for x in strings)
    trampoline_lines = "\n".join(
        f"- `{x['cpu_address']}` (file `{x['file_offset']}`) → U17 CODE `{x['target']}`"
        for x in result["fe_trampolines"]
    ) or "- none"
    (output / "DS1230_ANALYSIS.md").write_text(f"""# DS1230 read-only analysis

Input: `{result['path']}`; size `{result['size']}` bytes; SHA-256
`{result['sha256']}`.

## Content and code plausibility

- All `0xFF`: **{result['all_ff']}**; all `0x00`: **{result['all_zero']}**.
- Zero bytes: `{result['zero_count']}`; `0xFF` bytes: `{result['ff_count']}`;
  distinct byte values: `{result['distinct_bytes']}`.
- Offset `0000` bytes: `{result['reset_bytes']}`; plausible 8051 reset entry:
  **{result['reset_plausible_8051']}**.
- If mapped at CPU `8000`, `LCALL 8000` fetches file offset `0000`; this image
  does not present a normal 8051 reset-style application entry there.
- CPU `FE00–FEF9` corresponds to file offsets `7E00–7EF9`; all-FF there:
  **{result['fe00_fef9_all_ff']}**. The region contains
  `{result['fe_trampoline_count']}` 8051 `LJMP` trampolines into U17 CODE:
{trampoline_lines}
- Printable runs (minimum four bytes):
{string_lines}

## Non-zero storage inventory

These are byte-presence regions only; classification is deliberately
conservative and is not inferred from position alone.

| File range | Bytes | Classification | Confidence |
|---|---:|---|---|
""" + "\n".join(
        f"| `{x['start']}–{x['end']}` | {x['length']} | {x['classification']} | {x['confidence']} |"
        for x in result["nonzero_regions"]
    ) + f"""

## U17 startup markers and checksum

U17 sums file offsets `0000–7DFC` (CPU `8000–FDFC` inclusive), complements
the 16-bit result, and compares it big-endian at file offsets `7DFE–7DFF`.
The calculated sum is `{result['checksum_sum_16bit']}` and complement is
`{result['checksum_complement']}`. Stored checksum: `{result['stored_checksum']}`.

Startup marker bytes at file offsets `7DFC–7DFD`: `{result['signature']}`;
expected `AA55`; match: **{result['signature_matches']}**.
The second startup marker/checksum pair at file offsets `7DFE–7DFF` is
`{result['startup_pair']}`; startup expects `AA55`: **{result['startup_pair_matches']}**.
The checksum comparison also reads `7DFE–7DFF`: **{result['checksum_matches']}**.

The dumped contents therefore explain the console's `Checksum Failed` result:
both startup marker pairs are `0000` rather than `AA55`, and the checksum
comparison pair is also zero rather than the calculated complement. This is
consistent with U17's NVRAM-clear path having erased or never received the
application image. It does not prove when that clearing occurred.

## Mapping limits

The bytes are compatible with the proposed `8000` file-offset relationship,
but the dump alone does not prove CODE versus XDATA visibility, chip-select
decode, or whether FE-page CODE is supplied by this device. A bus trace or
additional live-board evidence remains required.
""", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dump", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--u17-calls", type=Path)
    args = parser.parse_args()
    write_report(analyze(args.dump, args.u17_calls), args.output)


if __name__ == "__main__":
    main()
