#!/usr/bin/env python3
"""Regression tests for the dependency-free U17 evidence extractor."""
from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASM = ROOT / "dyaxis/analysis/generated/u17/u17.reachable.asm"
ROM = ROOT / "dyaxis/firmware/original/41.005.415.Z1-U17-V1.06-AM27C256.bin"
SPEC = importlib.util.spec_from_file_location("deep_u17_analysis", Path(__file__).with_name("deep_u17_analysis.py"))
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class DeepU17Tests(unittest.TestCase):
    def test_known_vectors_and_rom_identity(self):
        data = ROM.read_bytes()
        self.assertEqual(len(data), 32768)
        self.assertEqual(data[:3], bytes.fromhex("022F6F"))
        self.assertEqual(data[0x23:0x26], bytes.fromhex("023416"))

    def test_address_space_separation(self):
        rows, labels, _ = MODULE.parse_asm(ASM, ROM.read_bytes())
        xrefs, _unknown, _states = MODULE.xdata_xrefs(rows, labels)
        calls = MODULE.external_calls(rows)
        self.assertTrue(any(address == "0xFFE1" and direction == "R" for address, direction, *_ in xrefs))
        self.assertTrue(any(address == "0xFFE1" and direction == "W" for address, direction, *_ in xrefs))
        self.assertTrue(any(address == "0xFFE3" and direction == "R" for address, direction, *_ in xrefs))
        self.assertTrue(any(target == "0xFED1" for _, _, target, _ in calls))
        self.assertFalse(any(target == "0xFFE1" for _, _, target, _ in calls))

    def test_synthetic_exact_addresses_and_dptr_invalidation(self):
        rom = bytearray([0] * 0x300)
        # 0100: MOV DPTR,#1234; MOVX; INC DPTR; MOVX; MOV DPL,A; MOVX.
        rom[0x100:0x10B] = bytes.fromhex("901234 E0 A3 E0 EF E0") + b"\x00\x00"
        asm = """org 100h
start:
    mov DPTR, #dptr_1234
    movx A, @DPTR
    inc DPTR
    movx A, @DPTR
    mov DPL, A
    movx A, @DPTR
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.asm"
            path.write_text(asm)
            rows, labels, _ = MODULE.parse_asm(path, bytes(rom))
            known, unknown, _states = MODULE.xdata_xrefs(rows, labels)
        self.assertEqual([row[2] for row in known], ["0x0103", "0x0105"])
        self.assertEqual(known[0][0], "0x1234")
        self.assertEqual(known[1][0], "0x1235")
        self.assertEqual(unknown[0][0], "0x0107")

    def test_synthetic_branch_merge_invalidates_dptr(self):
        rom = bytearray([0] * 0x300)
        rom[0x100:0x110] = bytes.fromhex("901234 60 05 905678 8003 E0 E0") + b"\x00\x00\x00\x00"
        asm = """org 100h
start:
    mov DPTR, #dptr_1234
    jz jump_010A
    mov DPTR, #dptr_5678
    sjmp jump_010D
jump_010A:
    movx A, @DPTR
jump_010D:
    movx A, @DPTR
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "branch.asm"
            path.write_text(asm)
            rows, labels, _ = MODULE.parse_asm(path, bytes(rom))
            known, unknown, _states = MODULE.xdata_xrefs(rows, labels)
        self.assertEqual(known[0][2], "0x010A")
        self.assertEqual(known[0][0], "0x1234")
        self.assertEqual(unknown[0][0], "0x010D")

    def test_referenced_strings_and_nonoverlapping_coverage(self):
        rom = bytearray([0] * 0x300)
        rom[0x200:0x205] = b"HELLO"
        rom[0x210:0x214] = b"NOPE"
        rows = [{"address": 0x100, "text": "mov DPTR, #dptr_0200", "function": "start", "ordinal": 0, "length": 3}]
        strings = MODULE.string_rows(bytes(rom), rows, [])
        self.assertEqual([row[1] for row in strings], ["referenced", "candidate"])
        stats = MODULE.coverage(rows, strings, [], len(rom))
        self.assertEqual(stats["overlap_conflict_bytes"], 0)
        self.assertEqual(stats["referenced_string_bytes"], 5)

    def test_synthetic_code_xdata_separation(self):
        rom = bytearray([0] * 0x300)
        asm = """org 100h
start:
    lcall jump_FE06
    mov DPTR, #dptr_1234
    movx A, @DPTR
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "spaces.asm"
            path.write_text(asm)
            rows, labels, _ = MODULE.parse_asm(path, bytes(rom))
            calls = MODULE.external_calls(rows)
            known, _unknown, _states = MODULE.xdata_xrefs(rows, labels)
        self.assertEqual(calls[0][2], "0xFE06")
        self.assertEqual(known[0][0], "0x1234")

    def test_register_constant_propagation_and_call_invalidation(self):
        rom = bytearray([0] * 0x200)
        rom[0x100:0x113] = bytes.fromhex("7A03 79C6 7B05 120000 79EA 120000") + b"\x00\x00"
        asm = """org 100h
start:
    mov R2, #03h
    mov R1, #0C6h
    mov R3, #05h
    lcall jump_FE06
    mov R1, #0EAh
    lcall jump_FE06
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "registers.asm"
            path.write_text(asm)
            rows, labels, _ = MODULE.parse_asm(path, bytes(rom))
            calls = MODULE.external_calls(rows)
            _xrefs, _unknown, dptr = MODULE.xdata_xrefs(rows, labels)
            resolved, _states = MODULE.resolved_register_abi(rows, labels, calls, dptr)
        self.assertEqual(resolved[0][14], "0x03C6")
        self.assertEqual(resolved[0][8], "R3=0x05")
        self.assertEqual(resolved[1][14], "?")

    def test_register_branch_merge_is_unknown(self):
        rom = bytearray([0] * 0x200)
        rom[0x100:0x110] = bytes.fromhex("7A03 6003 7A04 79C6 120000") + b"\x00\x00"
        asm = """org 100h
start:
    mov R2, #03h
    jz jump_0108
    mov R2, #04h
jump_0108:
    mov R1, #0C6h
    lcall jump_FE06
"""
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "register-merge.asm"
            path.write_text(asm)
            rows, labels, _ = MODULE.parse_asm(path, bytes(rom))
            calls = MODULE.external_calls(rows)
            _xrefs, _unknown, dptr = MODULE.xdata_xrefs(rows, labels)
            resolved, _states = MODULE.resolved_register_abi(rows, labels, calls, dptr)
        self.assertEqual(resolved[0][14], "?")

    def test_generation_emits_evidence_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            MODULE.generate(type("Args", (), {"asm": ASM, "rom": ROM, "out": out})())
            classification = json.loads((out / "u17-code-classification.json").read_text())
            self.assertGreater(classification["instruction_records"], 1000)
            self.assertGreater(classification["external_code_call_count"], 0)
            self.assertTrue((out / "U17_SERVICE_WINDOW.md").exists())
            self.assertIn("0xFFE1", (out / "u17-xdata-xrefs.tsv").read_text())
            self.assertIn("A8=02, A5=06", (out / "u17-state-transitions.tsv").read_text())

    def test_generation_separates_checksum_ranges_and_code_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            MODULE.generate(type("Args", (), {"asm": ASM, "rom": ROM, "out": out})())
            ranges = (out / "u17-checksum-ranges.tsv").read_text()
            memory = (out / "u17-memory-ranges.tsv").read_text()
            self.assertIn("checksum_input\t0x8000\t0xFDFC\thalf-open", ranges)
            self.assertIn("signature\t0xFDFC\t0xFDFD", ranges)
            self.assertIn("XDATA\t0xFE00\t0xFFFF\texternal service/peripheral window", memory)
            self.assertIn("CODE\t0xFE00\t0xFEF9\texternal service/shim code", memory)
            self.assertNotIn("CODE\t0xFFE1", memory)


if __name__ == "__main__":
    unittest.main()
