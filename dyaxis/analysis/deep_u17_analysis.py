#!/usr/bin/env python3
"""Evidence-first, ROM-backed analysis of the reachable U17 disassembly.

The disasm51 text identifies function starts but does not print an address on
every code line. This module reconstructs those addresses from labelled starts
and the original ROM's 8051 opcode lengths. XDATA results are produced only
when a control-flow data-flow pass proves the DPTR value at the MOVX.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict, deque
from pathlib import Path

LABEL_RE = re.compile(r"^(?P<label>[A-Za-z_][A-Za-z0-9_]*):\s*$")
ORG_RE = re.compile(r"^\s*org\s+(?P<value>[0-9A-Fa-f]+h|[A-Za-z_][A-Za-z0-9_]*)")
INS_RE = re.compile(r"^\s*(?P<text>[^;]+?)(?:\s*;\s*\[(?P<addr>[0-9A-Fa-f]+)h\])?(?:\s*;.*)?\s*$")
CALL_RE = re.compile(r"\b(?:lcall|acall)\s+(?P<target>[A-Za-z_][A-Za-z0-9_]*)")
TARGET_RE = re.compile(r"(?:jump|fwd)_([0-9A-Fa-f]{4})")
DPTR_LITERAL_RE = re.compile(r"#(?:dptr|fwd)_([0-9A-Fa-f]{4})")

ORG_SYMBOLS = {
    "RESET": 0x0000, "EXT0": 0x0003, "TIMER0": 0x000B,
    "EXT1": 0x0013, "TIMER1": 0x001B, "SIO0_UART": 0x0023,
    "SIO1_I2C": 0x002B, "T2_CAPTURE0": 0x0033, "T2_CAPTURE1": 0x003B,
    "T2_CAPTURE2": 0x0043, "T2_CAPTURE3": 0x004B, "ADC_COMPLETE": 0x0053,
    "T2_COMPARE0": 0x005B, "T2_COMPARE1": 0x0063, "T2_COMPARE2": 0x006B,
    "T2_OVERFLOW": 0x0073,
}

# Standard 8051 instruction lengths. Undefined opcodes remain one byte;
# reachable U17 rows are valid disasm51 output.
OPLEN = [1] * 256
for op in (0x01, 0x05, 0x11, 0x15, 0x21, 0x25, 0x31, 0x35,
           0x41, 0x42, 0x45, 0x51, 0x52, 0x55, 0x61, 0x62, 0x65,
           0x71, 0x72, 0x74, 0x76, 0x77, 0x78, 0x79, 0x7A, 0x7B,
           0x7C, 0x7D, 0x7E, 0x7F, 0x81, 0x82, 0x86, 0x87, 0x88,
           0x89, 0x8A, 0x8B, 0x8C, 0x8D, 0x8E, 0x8F, 0x91, 0x92,
           0x94, 0x95, 0xA0, 0xA1, 0xA2, 0xA6, 0xA7, 0xA8, 0xA9,
           0xAA, 0xAB, 0xAC, 0xAD, 0xAE, 0xAF, 0xB0, 0xB1, 0xB2,
           0xC0, 0xC1, 0xC2, 0xC5, 0xD0, 0xD1, 0xD2, 0xE1, 0xE5,
           0xF1, 0xF5):
    OPLEN[op] = 2
for op in (0x02, 0x10, 0x12, 0x20, 0x30, 0x43, 0x53, 0x63,
           0x75, 0x85, 0x90, 0xB4, 0xB5, 0xB6, 0xB7, 0xB8, 0xB9,
           0xBA, 0xBB, 0xBC, 0xBD, 0xBE, 0xBF, 0xD5):
    OPLEN[op] = 3

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

def label_address(name: str):
    match = re.match(r"(?:jump|fwd|dptr)_([0-9A-Fa-f]{4})(?:_|$)", name)
    return int(match.group(1), 16) if match else None

def instruction_length(rom: bytes, address: int | None) -> int:
    if address is None or address >= len(rom):
        return 1
    return OPLEN[rom[address]]

def parse_asm(path: Path, rom: bytes | None = None):
    rows, labels, label_addresses = [], {}, {}
    current = "(unlabeled)"
    cursor = None
    for line in path.read_text(errors="replace").splitlines():
        org = ORG_RE.match(line)
        if org:
            value = org.group("value")
            cursor = int(value[:-1], 16) if value.endswith("h") else ORG_SYMBOLS.get(value)
            continue
        label = LABEL_RE.match(line)
        if label:
            current = label.group("label")
            labels[current] = len(rows)
            numeric = label_address(current)
            if numeric is not None:
                cursor = numeric
            if cursor is not None:
                label_addresses[current] = cursor
            continue
        data_addr = re.search(r";\s*\[([0-9A-Fa-f]+)h\]", line)
        text_match = INS_RE.match(line)
        if not text_match:
            if data_addr:
                cursor = int(data_addr.group(1), 16) + 1
            continue
        text = text_match.group("text").strip()
        if not text or text.startswith(("db ", "db\t", "org", ";", "$", "cseg")):
            if data_addr:
                cursor = int(data_addr.group(1), 16) + 1
            continue
        explicit = text_match.group("addr")
        address = int(explicit, 16) if explicit else cursor
        length = instruction_length(rom or b"", address)
        rows.append({"address": address, "text": text, "function": current,
                     "ordinal": len(rows), "length": length})
        if address is not None:
            cursor = address + length
    return rows, labels, label_addresses

def address_text(row):
    return f"0x{row['address']:04X}" if row["address"] is not None else "unresolved-address"

def target_address(name):
    match = TARGET_RE.fullmatch(name) or re.fullmatch(r"dptr_([0-9A-Fa-f]{4})", name)
    return int(match.group(1), 16) if match else None

UNKNOWN = object()
UNSET = object()

def branch_target(text: str):
    tokens = re.findall(r"(?:jump|fwd)_[0-9A-Za-z_]+", text)
    return tokens[-1] if tokens else None

def successors(rows, labels, index):
    text = rows[index]["text"].lower()
    nxt = index + 1 if index + 1 < len(rows) else None
    if text.startswith(("ret", "reti")):
        return []
    target = branch_target(rows[index]["text"])
    if text.startswith(("ljmp ", "sjmp ", "ajmp ")):
        return [labels[target]] if target in labels else []
    if text.startswith(("j", "djnz ", "cjne ")) and target in labels:
        return [labels[target]] + ([nxt] if nxt is not None else [])
    return [nxt] if nxt is not None else []

def merge_state(old, new):
    if old is UNSET:
        return new
    if old is UNKNOWN or new is UNKNOWN:
        return UNKNOWN
    return old if old == new else UNKNOWN

def transfer_dptr(row, state):
    text = row["text"]
    literal = DPTR_LITERAL_RE.search(text)
    if literal:
        return int(literal.group(1), 16)
    if re.search(r"\b(?:lcall|acall)\b", text):
        return UNKNOWN
    if re.search(r"\b(?:pop|mov)\s+DPH\b", text) or re.search(r"\b(?:pop|mov)\s+DPL\b", text):
        if "mov DPTR" not in text or "#" not in text:
            return UNKNOWN
    if re.search(r"\binc\s+DPTR\b", text, re.I):
        return (state + 1) & 0xFFFF if isinstance(state, int) else UNKNOWN
    if re.search(r"\b(?:mov|inc|dec|add|subb|xch)\s+DPH\b", text, re.I):
        return UNKNOWN
    if re.search(r"\b(?:mov|inc|dec|add|subb|xch)\s+DPL\b", text, re.I):
        return UNKNOWN
    return state

def dptr_dataflow(rows, labels):
    incoming = [UNSET] * len(rows)
    queue = deque()
    branch_refs, call_refs = set(), set()
    for row in rows:
        target = branch_target(row["text"])
        if target:
            if re.search(r"\b(?:lcall|acall)\b", row["text"]):
                call_refs.add(target)
            else:
                branch_refs.add(target)
    roots = {0}
    roots.update(index for name, index in labels.items()
                if index < len(rows) and name not in branch_refs)
    for root in roots:
        incoming[root] = merge_state(incoming[root], UNKNOWN)
        queue.append(root)
    while queue:
        index = queue.popleft()
        outgoing = transfer_dptr(rows[index], incoming[index])
        for successor in successors(rows, labels, index):
            if successor is None:
                continue
            merged = merge_state(incoming[successor], outgoing)
            if merged != incoming[successor]:
                incoming[successor] = merged
                queue.append(successor)
    return incoming

def xdata_xrefs(rows, labels):
    states = dptr_dataflow(rows, labels)
    known, unknown = [], []
    for index, row in enumerate(rows):
        if "movx" not in row["text"].lower():
            continue
        state = states[index]
        if not isinstance(state, int):
            unknown.append((address_text(row), row["function"], row["text"]))
            continue
        if "movx A, @DPTR" in row["text"]:
            direction = "R"
        elif "movx @DPTR, A" in row["text"]:
            direction = "W"
        else:
            continue
        known.append((f"0x{state:04X}", direction, address_text(row), row["function"], row["text"]))
    return known, unknown, states

REGISTER_NAMES = ("A", "B", "R0", "R1", "R2", "R3", "R4", "R5", "R6", "R7")

def unknown_registers():
    return {name: UNKNOWN for name in REGISTER_NAMES}

def parse_imm(text):
    match = re.search(r"#([0-9A-Fa-f]{1,3})h", text)
    return int(match.group(1), 16) if match else None

def transfer_registers(row, state):
    result = dict(state)
    text = row["text"]
    if re.search(r"\b(?:lcall|acall)\b", text):
        return unknown_registers()
    immediate = parse_imm(text)
    match = re.search(r"\bmov\s+(A|B|R[0-7]),\s*#", text)
    if match and immediate is not None:
        result[match.group(1)] = immediate
        return result
    if re.search(r"\bclr\s+A\b", text):
        result["A"] = 0
    match = re.search(r"\bmov\s+(A|B|R[0-7]),\s*(A|B|R[0-7])\b", text)
    if match:
        result[match.group(1)] = result[match.group(2)]
        return result
    match = re.search(r"\bmov\s+(R[0-7]),\s*(?:direct|@|DPTR|[0-9A-Fa-f]+h)", text, re.I)
    if match:
        result[match.group(1)] = UNKNOWN
    if re.search(r"\bmov\s+(?:A|B),\s*(?:direct|@|DPTR|[0-9A-Fa-f]+h)", text, re.I):
        result[re.search(r"\bmov\s+(A|B)", text, re.I).group(1).upper()] = UNKNOWN
    match = re.search(r"\b(?:inc|dec)\s+(R[0-7])\b", text, re.I)
    if match:
        old = result[match.group(1)]
        if isinstance(old, int):
            result[match.group(1)] = (old + (1 if text.lower().startswith("inc") else -1)) & 0xFF
        else:
            result[match.group(1)] = UNKNOWN
    if re.search(r"\bmovx\s+A", text, re.I):
        result["A"] = UNKNOWN
    if re.search(r"\b(?:add|addc|subb|anl|orl|xrl|rr|rl|rrc|rlc|swap|da)\s+A", text, re.I):
        result["A"] = UNKNOWN
    match = re.search(r"\bxch\s+A,\s*(R[0-7])", text, re.I)
    if match:
        other = match.group(1)
        result["A"], result[other] = result[other], result["A"]
    if re.search(r"\bpop\s+(?:A|B|R[0-7])\b", text, re.I):
        result[re.search(r"\bpop\s+(A|B|R[0-7])", text, re.I).group(1).upper()] = UNKNOWN
    return result

def merge_registers(old, new):
    if old is UNSET:
        return dict(new)
    merged = {}
    for name in REGISTER_NAMES:
        if old[name] is UNKNOWN or new[name] is UNKNOWN:
            merged[name] = UNKNOWN
        else:
            merged[name] = old[name] if old[name] == new[name] else UNKNOWN
    return merged

def register_dataflow(rows, labels):
    incoming = [UNSET] * len(rows)
    queue = deque()
    branch_refs = set()
    for row in rows:
        target = branch_target(row["text"])
        if target and not re.search(r"\b(?:lcall|acall)\b", row["text"]):
            branch_refs.add(target)
    roots = {0}
    roots.update(index for name, index in labels.items()
                 if index < len(rows) and name not in branch_refs)
    for root in roots:
        incoming[root] = merge_registers(incoming[root], unknown_registers())
        queue.append(root)
    while queue:
        index = queue.popleft()
        outgoing = transfer_registers(rows[index], incoming[index])
        for successor in successors(rows, labels, index):
            if successor is None:
                continue
            merged = merge_registers(incoming[successor], outgoing)
            if incoming[successor] is UNSET or any(merged[name] != incoming[successor][name] for name in REGISTER_NAMES):
                incoming[successor] = merged
                queue.append(successor)
    return incoming

def resolved_register_abi(rows, labels, calls, dptr_states):
    states = register_dataflow(rows, labels)
    by_address = {row["address"]: index for index, row in enumerate(rows) if row["address"] is not None}
    output = []
    for location, caller, target, _instruction in calls:
        index = by_address.get(int(location, 16))
        if index is None or states[index] is UNSET:
            continue
        values = states[index]
        pointer = ((values["R2"] << 8) | values["R1"]) if isinstance(values["R2"], int) and isinstance(values["R1"], int) else "unknown"
        rendered = [f"{name}=0x{values[name]:02X}" if isinstance(values[name], int) else f"{name}=?" for name in REGISTER_NAMES]
        post = "; ".join(row["text"] for row in rows[index + 1:index + 5])
        output.append((location, caller, target, *rendered,
                       f"0x{dptr_states[index]:04X}" if isinstance(dptr_states[index], int) else "?",
                       f"0x{pointer:04X}" if isinstance(pointer, int) else "?", post))
    return output, states

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

def printable_strings(rom: bytes, minimum=4):
    found, start = [], None
    for index, byte in enumerate(rom + b"\x00"):
        printable = 0x20 <= byte <= 0x7E
        if printable and start is None:
            start = index
        elif not printable and start is not None:
            if index - start >= minimum:
                found.append((start, rom[start:index].decode("ascii", "replace")))
            start = None
    return found

def movc_tables(rows, labels, rom, states):
    tables = defaultdict(lambda: {"sites": [], "indices": set(), "masks": set(), "jump": False})
    for index, row in enumerate(rows):
        if "movc A, @A" not in row["text"]:
            continue
        base = states[index]
        if not isinstance(base, int) or base >= len(rom):
            tables[None]["sites"].append(row)
            continue
        entry = tables[base]
        entry["sites"].append(row)
        if index + 1 < len(rows) and "jmp @A+DPTR" in rows[index + 1]["text"]:
            entry["jump"] = True
        for previous in reversed(rows[max(0, index - 12):index]):
            match = re.search(r"mov A, #([0-9A-Fa-f]{1,2})h", previous["text"])
            mask = re.search(r"anl A, #([0-9A-Fa-f]{1,2})h", previous["text"])
            if match:
                entry["indices"].add(int(match.group(1), 16))
                break
            if mask:
                entry["masks"].add(int(mask.group(1), 16))
                break
            if re.search(r"\b(?:movx A|mov A,|clr A)\b", previous["text"]):
                break
    output = []
    for base, entry in sorted(tables.items(), key=lambda item: (-1 if item[0] is None else item[0])):
        if base is None:
            output.append(("unknown", "unknown", "unknown", "; ".join(address_text(row) for row in entry["sites"]), "unresolved"))
            continue
        indices = sorted(entry["indices"])
        extent = (max(mask + 1 for mask in entry["masks"])
                  if entry["masks"] else (max(indices) + 1 if indices else None))
        sample = rom[base:base + extent] if extent else b""
        if entry["jump"]:
            kind = "jump table"
        elif sample and sum(0x20 <= value <= 0x7E for value in sample) / len(sample) > 0.7:
            kind = "display/text data"
        elif extent:
            kind = "lookup table"
        else:
            kind = "unknown table"
        output.append((f"0x{base:04X}", str(extent or "unknown"), kind,
                       "; ".join(address_text(row) + " " + row["function"] for row in entry["sites"]),
                       "bounded" if extent else "unbounded"))
    return output

def string_rows(rom, rows, tables, extra_refs=None):
    strings = printable_strings(rom)
    refs = defaultdict(list)
    for row in rows:
        for match in re.finditer(r"(?:dptr|fwd)_([0-9A-Fa-f]{4})", row["text"]):
            refs[int(match.group(1), 16)].append(address_text(row) + " " + row["function"])
    for base, _length, _kind, _sites, _resolution in tables:
        if base.startswith("0x"):
            refs[int(base, 16)].append("MOVC table")
    for address, sites in (extra_refs or {}).items():
        refs[address].extend(sites)
    result = []
    for address, text in strings:
        matching = []
        for base, sites in refs.items():
            if address <= base < address + len(text):
                matching.extend(sites)
        result.append((f"0x{address:04X}", "referenced" if matching else "candidate", "; ".join(matching), text))
    return result

def write_tsv(path, header, rows):
    with path.open("w", encoding="utf-8") as handle:
        handle.write("\t".join(header) + "\n")
        for row in rows:
            line = "\t".join(str(value).replace("\t", " ").rstrip() for value in row)
            handle.write(line.rstrip() + "\n")

def coverage_sets(rows, string_data, tables, rom_size):
    categories = defaultdict(set)
    for row in rows:
        if row["address"] is not None:
            categories["instruction"].update(range(row["address"], min(rom_size, row["address"] + row["length"])))
    for base, length, _kind, _sites, bounded in tables:
        if base.startswith("0x") and length != "unknown" and bounded == "bounded":
            categories["table"].update(range(int(base, 16), min(rom_size, int(base, 16) + int(length))))
    for address, status, _sites, text in string_data:
        category = "referenced_string" if status == "referenced" else "candidate_string"
        categories[category].update(range(int(address, 16), min(rom_size, int(address, 16) + len(text))))
    return categories

def coverage(rows, string_data, tables, rom_size):
    categories = coverage_sets(rows, string_data, tables, rom_size)
    owners = defaultdict(set)
    for category, addresses in categories.items():
        for address in addresses:
            owners[address].add(category)
    union = set(owners)
    conflicts = {address for address, values in owners.items() if len(values) > 1}
    values = {
        "rom_bytes": rom_size, "reachable_instruction_bytes": len(categories["instruction"]),
        "referenced_table_bytes": len(categories["table"]), "referenced_string_bytes": len(categories["referenced_string"]),
        "candidate_string_bytes": len(categories["candidate_string"]), "unclassified_bytes": rom_size - len(union),
        "overlap_conflict_bytes": len(conflicts),
    }
    values["percentages"] = {key: round(value * 100 / rom_size, 3) for key, value in values.items()
                              if key.endswith("bytes") and key != "rom_bytes"}
    return values

def unclassified_ranges(rom, rows, string_data, tables):
    classified = set().union(*coverage_sets(rows, string_data, tables, len(rom)).values())
    ranges, start = [], None
    for address in range(len(rom) + 1):
        if address < len(rom) and address not in classified and start is None:
            start = address
        elif (address == len(rom) or address in classified) and start is not None:
            end = address - 1
            linear = sum(1 for candidate in range(start, end + 1)
                         if rom[candidate] == 0x12 and candidate + 2 < len(rom)
                         and ((rom[candidate + 1] << 8) | rom[candidate + 2]) < 0x8000)
            pointer_words = sum(1 for candidate in range(start, end)
                                if ((rom[candidate] << 8) | rom[candidate + 1]) < 0x8000)
            ranges.append((f"0x{start:04X}", f"0x{end:04X}", end - start + 1,
                           linear, pointer_words, "linear candidates only"))
            start = None
    return ranges

def fe_abi(rows, calls):
    by_address = {row["address"]: index for index, row in enumerate(rows) if row["address"] is not None}
    output = []
    for location, caller, target, _instruction in calls:
        index = by_address.get(int(location, 16))
        if index is None:
            continue
        target_int = int(target, 16)
        if target_int == 0x8000:
            family, confidence = "external application launch", "high"
        elif 0xFEC0 <= target_int <= 0xFEF9:
            family, confidence = "interrupt/service shim", "medium"
        else:
            family, confidence = "FE-page service", "low"
        pre = rows[max(0, index - 6):index]
        post = rows[index + 1:index + 7]
        reg_re = re.compile(r"\b(?:mov|setb|clr|inc|dec|add|anl|orl|xrl)\s+(?:A|R[0-7]|DPH|DPL|DPTR|IEN[01]|TM\w+|P[0-7])")
        context_re = re.compile(r"movx|DPTR|SBUF|S0|S1|SCON|TM\w+|IEN[01]|P[0-7]", re.I)
        pre_regs = "; ".join(row["text"] for row in pre if reg_re.search(row["text"]) or context_re.search(row["text"]))
        post_regs = "; ".join(row["text"] for row in post if reg_re.search(row["text"]) or context_re.search(row["text"]))
        output.append((location, caller, target, family, confidence, pre_regs, post_regs))
    return output

def generate(args):
    rom = args.rom.read_bytes()
    rows, labels, _label_addresses = parse_asm(args.asm, rom)
    xrefs, unknown_xrefs, states = xdata_xrefs(rows, labels)
    calls = external_calls(rows)
    resolved_abi, register_states = resolved_register_abi(rows, labels, calls, states)
    tables = movc_tables(rows, labels, rom, states)
    fe06_rows = [row for row in resolved_abi if row[2] == "0xFE06"]
    string_refs = defaultdict(list)
    for row in fe06_rows:
        if row[14] != "?":
            string_refs[int(row[14], 16)].append(f"FE06 {row[0]} {row[1]}")
    strings = string_rows(rom, rows, tables, string_refs)
    abi = fe_abi(rows, calls)
    unclassified = unclassified_ranges(rom, rows, strings, tables)
    abi_groups = defaultdict(list)
    for row in abi:
        abi_groups[(row[2], row[3], row[4])].append(row[0])
    coverage_data = coverage(rows, strings, tables, len(rom))
    args.out.mkdir(parents=True, exist_ok=True)

    write_tsv(args.out / "u17-xdata-xrefs.tsv", ["address", "direction", "rom_address", "function", "instruction"], xrefs)
    write_tsv(args.out / "u17-xdata-unknown.tsv", ["rom_address", "function", "instruction"], unknown_xrefs)
    write_tsv(args.out / "u17-external-code-dependencies.tsv", ["rom_address", "caller", "target", "instruction"], calls)
    write_tsv(args.out / "u17-fe-abi.tsv", ["rom_address", "caller", "target", "family", "confidence", "inputs_before", "outputs_after"], abi)
    write_tsv(args.out / "u17-register-resolved-abi.tsv",
              ["rom_address", "caller", "target", *REGISTER_NAMES, "DPTR", "R2_R1_CODE_POINTER", "post_call"], resolved_abi)
    write_tsv(args.out / "u17-fe06-calls.tsv",
              ["rom_address", "caller", "target", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "CODE_pointer_R2_R1", "post_call"],
              [(row[0], row[1], row[2], row[6], row[7], row[8], row[9], row[10], row[11], row[12], row[14], row[15]) for row in fe06_rows])
    write_tsv(args.out / "u17-unclassified-ranges.tsv",
              ["start", "end", "byte_count", "linear_lcall_candidates", "pointer_word_candidates", "status"], unclassified)
    write_tsv(args.out / "u17-fe-abi-summary.tsv", ["target", "family", "confidence", "call_count", "call_sites"],
              [(target, family, confidence, len(sites), "; ".join(sites))
               for (target, family, confidence), sites in sorted(abi_groups.items())])
    write_tsv(args.out / "u17-movc-tables.tsv", ["base", "bounded_length", "classification", "call_sites", "resolution"], tables)
    write_tsv(args.out / "u17-indirect-targets.tsv", ["rom_address", "function", "instruction"],
              [(address_text(row), row["function"], row["text"])
               for row in rows if "movc" in row["text"].lower() or "jmp @A+DPTR" in row["text"]])
    write_tsv(args.out / "u17-string-inventory.tsv", ["rom_address", "classification", "references", "text"], strings)
    write_tsv(args.out / "u17-referenced-strings.tsv", ["rom_address", "references", "text"], [row for row in strings if row[1] == "referenced"])
    write_tsv(args.out / "u17-string-candidates.tsv", ["rom_address", "text"], [(row[0], row[3]) for row in strings if row[1] == "candidate"])
    write_tsv(args.out / "u17-state-transitions.tsv", ["condition", "code", "effect", "confidence"], STATE_ROWS)

    # These ranges are emitted from instruction-level facts visible in the
    # reachable listing, not from a presumed board schematic.  The physical
    # device assignment is deliberately kept separate in the markdown report.
    memory_ranges = [
        ("CODE", "0x0000", "0x7FFF", "U17 EPROM", "confirmed physical device and address range"),
        ("XDATA", "0x0000", "0x7FFF", "working RAM", "confirmed startup clear; U18 assignment is strong hardware hypothesis"),
        ("XDATA", "0x8000", "0xFDFC", "persistent/application window", "confirmed checksum and transfer accesses; DS1230 assignment is hardware hypothesis"),
        ("XDATA", "0xFDFD", "0xFDFD", "signature byte", "confirmed read by startup; not cleared by the observed clear loop"),
        ("XDATA", "0xFDFE", "0xFDFF", "complemented checksum", "confirmed read/clear and compared with checksum result"),
        ("XDATA", "0xFE00", "0xFFFF", "external service/peripheral window", "confirmed separately cleared and accessed; not proven DS1230 storage"),
        ("CODE", "0x8000", "0x8000", "application entry", "confirmed LCALL after validation; provider is external to U17"),
        ("CODE", "0xFE00", "0xFEF9", "external service/shim code", "confirmed executable CODE targets; provider unresolved"),
    ]
    write_tsv(args.out / "u17-memory-ranges.tsv", ["space", "start", "end", "observed_role", "evidence"], memory_ranges)
    checksum_ranges = [
        ("checksum_input", "0x8000", "0xFDFC", "half-open [start,end)", "sum bytes 0x8000..0xFDFC inclusive; complement in R6:R7"),
        ("checksum_result", "0xFDFE", "0xFDFF", "stored big-endian comparison bytes", "compared against complemented sum at 0x02D7..0x0304"),
        ("signature", "0xFDFC", "0xFDFD", "AA 55", "startup gate at 0x0293..0x02AC"),
        ("clear_application", "0x8000", "0xFDFD", "half-open [start,end)", "clear loop 0x03A4..0x03BE"),
        ("clear_checksum", "0xFDFE", "0xFFFF", "half-open [start,end)", "two explicit zero writes at 0x03BE..0x03C5"),
    ]
    write_tsv(args.out / "u17-checksum-ranges.tsv", ["kind", "start", "end", "range_semantics", "evidence"], checksum_ranges)
    update_writes = [
        ("0x2F7D", "MOVX @DPTR,A", "0x0000..0x7FFF", "reset working-RAM clear; DPTR increments, outer count 0x80"),
        ("0x2F8B", "MOVX @DPTR,A", "0xFE00..0xFFFF", "separate service/peripheral-window clear; outer count 0x01"),
        ("0x03A4", "MOVX @DPTR,A", "0x8000..0xFDFC", "application/persistent-window clear"),
        ("0x03BE", "MOVX @DPTR,A", "0xFDFE..0xFDFF", "checksum bytes cleared"),
        ("0x321C", "MOVX @DPTR,A", "0x8000 + block*0x80", "received byte write; block/index A5 must be < 0xFC; destination pointer in 9E:9F"),
        ("0x327E", "MOVX @FFE3,A", "0xFFE3", "service output, not application storage"),
    ]
    write_tsv(args.out / "u17-update-writes.tsv", ["rom_address", "instruction", "destination", "evidence"], update_writes)

    high = defaultdict(lambda: {"R": 0, "W": 0, "locations": []})
    for address, direction, location, function, text in xrefs:
        value = int(address, 16)
        if 0xFFE0 <= value <= 0xFFFF:
            high[value][direction] += 1
            high[value]["locations"].append(f"{location} {function}: {text}")
    function_count = len([name for name in labels if name.startswith(("jump_", "fwd_")) or name in ("RESET_TARGET", "SERIAL_ISR")])
    classification = {
        "method": "disasm51 reachable boundaries plus ROM-backed 8051 address reconstruction and CFG DPTR analysis",
        "instruction_records": len(rows), "function_labels": function_count,
        "external_code_call_count": len(calls), "resolved_movc_table_count": sum(1 for row in tables if row[0].startswith("0x")),
        "unresolved_movc_count": sum(1 for row in tables if row[0] == "unknown"),
        "unclassified_range_count": len(unclassified), "fe06_call_count": len(fe06_rows),
        "literal_high_xdata": {f"0x{address:04X}": value for address, value in sorted(high.items())},
        "coverage": coverage_data,
        "limits": ["External CODE bodies are outside the U17 image.", "Unknown or merged DPTR states are excluded from XDATA claims.", "Referenced string detection is limited to literal ROM pointers and MOVC bases."],
    }
    (args.out / "u17-code-classification.json").write_text(json.dumps(classification, indent=2) + "\n", encoding="utf-8")
    referenced_strings = sum(1 for row in strings if row[1] == "referenced")
    candidate_strings = sum(1 for row in strings if row[1] == "candidate")
    reachable_bytes = coverage_data["reachable_instruction_bytes"]
    (args.out / "U17_COMPLETE_PROGRAM_MAP.md").write_text(f"""# U17 current reachable-vector map

Generated from `{args.asm.name}` and the verified tracked ROM. The current
pass reconstructs exact ROM addresses for **{len(rows)} valid instructions**
covering **{reachable_bytes} bytes**. It is not a complete program map: bytes
outside reachable vector paths, unresolved indirect control flow and external
CODE bodies remain separate evidence domains.

Referenced strings: **{referenced_strings}**; printable candidates not
referenced by a literal ROM pointer or resolved MOVC base: **{candidate_strings}**.
See `u17-code-classification.json` for complete byte coverage and percentages.

## Confirmed entry families

- Reset/startup: `0x0000 -> 0x2F6F -> 0x2FD2 -> 0x01E0`.
- Local checks/services: `0x037C`, `0x03A4`, `0x032F`, `0x034D`, `0x1440`.
- Main service state machine: `0x30A7..0x328A`.
- Interrupt shims: `0x33F8`, `0x3416`, `0x3434`, `0x3452`, `0x3470`,
  `0x348E`, `0x34AC..0x357E`.

Exact instruction addresses are present in generated TSVs. MOVC tables are in
`u17-movc-tables.tsv`; only bounded target sets are eligible for promotion.
""", encoding="utf-8")
    fe33_rows = [row for row in resolved_abi if row[2] == "0xFE33"]
    fe33_r7 = [row[12] for row in fe33_rows[:8]]
    (args.out / "U17_EXTERNAL_CODE_DEPENDENCIES.md").write_text(f"""# U17 external CODE dependencies

The current reachable U17 image makes **{len(calls)}** literal external CODE
call references. Exact call-site addresses and targets are in
`u17-external-code-dependencies.tsv`; call-site register/memory context is in
`u17-fe-abi.tsv`; grouped target/family counts are in `u17-fe-abi-summary.tsv`.

FE-page groups are separated into ordinary FE-page service calls and
`0xFEC0..0xFEF9` interrupt/service shims. Context is evidence for inputs and
post-return observations; a single call is not promoted into a display,
serial, timer or storage API without repeated supporting sites.

`LCALL` targets in `0xFE00..0xFEF9` are external CODE: the P80C552 fetches
executable instructions there. They are not ordinary peripheral registers.
Possible sources are mapped persistent memory such as the DS1230 window,
executable RAM, or FPGA/PAL-supplied bus behavior; MOVX peripheral accesses
remain a separate address-space category. The U17 image cannot identify the
physical provider by itself.

`FE06` has {len(fe06_rows)} resolved calls with CODE pointers in `R2:R1`; see
`U17_FE06_DISPLAY_ABI.md`. `FE33` has {len(fe33_rows)} calls. Its first eight
repeated sites pass `R7` values {', '.join(fe33_r7)}, with `A`, `R4` and `R5`
zero at those sites. This supports a repeated indexed initialization/service
family, but does not prove whether it initializes display, timing, serial or
another subsystem. `LCALL 0x8000` remains a distinct external-code launch.
""", encoding="utf-8")
    r3_values = sorted({row[8] for row in fe06_rows})
    r5_values = sorted({row[10] for row in fe06_rows})
    fe06_strings = [row for row in strings if row[1] == "referenced" and any("FE06" in ref for ref in row[2].split("; "))]
    (args.out / "U17_FE06_DISPLAY_ABI.md").write_text(f"""# U17 FE06 display/string ABI

The resolved call-site data-flow pass finds **{len(fe06_rows)}** calls to
external CODE `0xFE06` with definite register values. In every definite case,
`R2:R1` is a 16-bit CODE-space pointer into the U17 ROM and resolves to one of
the embedded boot/status strings. This is strong evidence that `FE06` is an
external display/string service, not an XDATA peripheral register.

| Field | Observed evidence | Interpretation |
|---|---|---|
| `R2:R1` | Pointers resolve to `{len(fe06_strings)}` embedded strings | Confirmed CODE-space string pointer |
| `R3` | Values: {', '.join(r3_values)} | Meaning unresolved; compare with display layout before assigning |
| `R5` | Values: {', '.join(r5_values)} | Meaning unresolved; repeated values may encode an operation/style/destination, but no assignment is proven |
| `R4`, `R6`, `R7` | Recorded per call in `u17-fe06-calls.tsv` | Inputs are preserved; no unsupported semantic label |

The exact pointer, caller, all resolved register values and nearby post-call
instructions are in `u17-register-resolved-abi.tsv`. The FE06-specific view is
`u17-fe06-calls.tsv`; referenced strings are in
`u17-referenced-strings.tsv`.

No screen-row or column meaning is assigned to R3/R5 from static code alone.
Photographed display geometry and a passive bus trace are required for that
mapping.
""", encoding="utf-8")
    (args.out / "U17_MEMORY_MAP.md").write_text("""# U17 memory map: evidence and hardware hypotheses

This report separates address-space facts recovered from U17 instructions from
physical-chip assignments inferred from the new board photographs.

| Space/range | Static evidence | Physical interpretation | Confidence |
|---|---|---|---|
| CODE `0000..7FFF` | U17 is a 32 KiB EPROM; reset and reachable code occupy this range | U17 AMD AM27C256 | Confirmed |
| XDATA `0000..7FFF` | Reset loop at `2F7D` writes zero for `0x8000` bytes | U18 Toshiba TC55257BSPL-10 is the strongest volatile-RAM candidate | Strong hardware hypothesis |
| XDATA `8000..FDFC` | Checksum loop `037C` and clear loop `03A4` access this span | DS1230-backed persistent/application region is the best fit | Strong hypothesis |
| XDATA `FDFC..FDFF` | Signature and checksum metadata are read; checksum bytes are explicitly cleared | Likely persistent metadata within the same upper RAM device | Strong hypothesis |
| XDATA `FE00..FFFF` | Reset loop at `2F8B` clears this range separately; service accesses include `FFE1/FFE3`, `FFF0/FFF1`, `FFF4/FFF5` | External peripheral/service decode, not proven DS1230 storage | Strong static conclusion; exact devices unresolved |
| CODE `8000` | `328A` executes `LCALL 8000` after validation | External application entry, provider unresolved | Confirmed code behavior |
| CODE `FE00..FEF9` | Literal `LCALL` targets and interrupt shims | Mapped executable provider, possibly persistent memory, executable RAM or FPGA/PAL bus logic | Confirmed target; provider unresolved |

The `u17-memory-ranges.tsv`, `u17-checksum-ranges.tsv` and
`u17-update-writes.tsv` files are the machine-readable evidence tables. CODE
fetches are never treated as MOVX/XDATA peripheral accesses.
""", encoding="utf-8")
    (args.out / "U17_DS1230_LAYOUT.md").write_text("""# U17 DS1230 layout: preservation hypothesis

The new photograph identifies a Dallas `DS1230Y-100` 32K x 8 battery-backed
nonvolatile SRAM on the U17 board. It is preservation-critical, but the ROM
does not prove the chip-select wiring or address decode.

## Best-supported layout

| Range | Evidence | Assessment |
|---|---|---|
| `8000..FDFC` | Reset clear, receive transfer writes, checksum input | Strong candidate for persistent application/data contents |
| `FDFC..FDFF` | `AA 55` signature at `FDFC/FDFD`; complemented checksum compared at `FDFE/FDFF` | Candidate persistent header/trailer; exact ownership is not electrically proven |
| `FE00..FFFF` | Separately cleared at reset and used for service windows | Evidence weighs against mapping this entire range to DS1230 storage |

The DS1230 is 32 KiB, while `8000..FDFF` is `0x7E00` bytes; therefore the
remaining `0x0200` bytes of a full 32 KiB device could be bank-select,
reserved, mirrored, or part of an unobserved decode. A simple one-to-one
`8000..FFFF` assignment is not established. The most conservative statement
is “DS1230 is a plausible source for the persistent upper application window;
the FE page is separately decoded until bus evidence says otherwise.”

Do not read it with an EPROM definition or remove it. A safe preservation path
is first a powered-off, non-invasive pinout/continuity review and chip-select
trace, followed by a reviewed high-impedance in-system read plan. The plan
must account for the age of the internal battery and preserve power state; no
powered probing, write/update, blank-check, erase, or programmer operation is
authorized by this report. If the read plan is approved, acquire three
read-only dumps with an independently verified byte count and SHA-256 while
preserving the raw captures separately from U17 executable code.
""", encoding="utf-8")
    (args.out / "U17_UPDATE_AND_LAUNCH_PATH.md").write_text("""# U17 update, validation and launch path

## Confirmed sequence

1. `2F7D` clears XDATA `0000..7FFF` (the endpoint is exclusive).
2. `2F8B` separately clears XDATA `FE00..FFFF`.
3. `03A4` clears `8000..FDFC` and then explicitly clears `FDFE/FDFF`.
4. `31C1` accepts block/index values `0x00..0xFB`, computes
   `0x8000 + index*0x80`, and stores the received byte stream through the
   pointer held in internal RAM `9E:9F`; `321C` performs the `MOVX` write.
5. `037C` sums bytes in half-open range `[8000,FDFD)`, i.e. through `FDFC`,
   with 16-bit carry and returns the bitwise-complement in `R6:R7`.
6. Startup checks `FDFC/FDFD == AA 55`, then compares the complemented sum
   with `FDFE/FDFF`.
7. The success path calls `328A`, which disables services and executes
   `LCALL 8000`; the launched code is expected to return through the observed
   call frame before U17's reset-target call.

The block bound implies a maximum block start of `FD80` and a final 128-byte
block ending at `FDFF`. This is a transfer bound, not proof that every byte is
valid application code. Exact writes are listed in `u17-update-writes.tsv`.

## Unresolved

The wire framing, header fields, completion marker, checksum byte order as
sent by the host, and physical DS1230 chip-select mapping require a passive
bus/serial observation or a reviewed non-destructive memory read. No active
update should be attempted.
""", encoding="utf-8")
    (args.out / "U17_SERVICE_WINDOW.md").write_text("""# U17 FFE1/FFE3 service-window analysis

Only MOVX instructions with a CFG-proven DPTR value are included in
`u17-xdata-xrefs.tsv`. Instructions with unknown or merged DPTR state are
listed in `u17-xdata-unknown.tsv` and are not assigned an address.

`FFE1` is read at `30AA` and `3253`, and written by `3332` and `3348`.
`FFE3` is read by `30C3` and written by `327E`. The conservative interpretation
is a candidate FPGA/peripheral service-register window, possibly decoded or
controlled by PAL logic. It is not proven to be a Macintosh protocol or a
PAL-owned mailbox.
""", encoding="utf-8")
    (args.out / "U17_STARTUP_STATE_MACHINE.md").write_text("""# U17 startup state machine

```text
0000 -> 2F6F: clear internal RAM; clear XDATA 0000..7FFF and FE00..FFFF
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
""", encoding="utf-8")
    (args.out / "U17_SERIAL_AND_HOST_PROTOCOL.md").write_text("""# U17 serial and host-protocol boundary

The SIO0 vector at `0023` reaches `3416`. That ISR reads XDATA `FED0`, loads
PSW from the returned byte, calls external CODE `FED1`, restores context and
returns `RETI`. The FE-page call-site ABI table is `u17-fe-abi.tsv`.

U17 contains no reachable direct S0CON/S0BUF/TH1/TMOD setup in this pass.
Framing, buffers, escape bytes, lengths, checksums, Z85230 channel selection
and baud therefore remain unproven. Passive capture or an external-bus trace
is required.
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
inferential.
""", encoding="utf-8")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("asm", type=Path)
    parser.add_argument("rom", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    if args.rom.stat().st_size != 32768:
        raise SystemExit("U17 ROM must be exactly 32768 bytes")
    generate(args)

if __name__ == "__main__":
    main()
