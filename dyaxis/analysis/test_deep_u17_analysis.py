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
        rows, _ = MODULE.parse_asm(ASM)
        xrefs = MODULE.xdata_xrefs(rows)
        calls = MODULE.external_calls(rows)
        self.assertTrue(any(address == 0xFFE1 and direction == "R" for address, direction, *_ in xrefs))
        self.assertTrue(any(address == 0xFFE1 and direction == "W" for address, direction, *_ in xrefs))
        self.assertTrue(any(address == 0xFFE3 and direction == "R" for address, direction, *_ in xrefs))
        self.assertTrue(any(target == "0xFED1" for _, _, target, _ in calls))
        self.assertFalse(any(target == "0xFFE1" for _, _, target, _ in calls))

    def test_generation_emits_evidence_tables(self):
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            MODULE.generate(type("Args", (), {"asm": ASM, "rom": ROM, "out": out})())
            classification = json.loads((out / "u17-code-classification.json").read_text())
            self.assertGreater(classification["instruction_count"], 1000)
            self.assertGreater(classification["external_code_call_count"], 0)
            self.assertTrue((out / "U17_SERVICE_WINDOW.md").exists())
            self.assertIn("0xFFE1", (out / "u17-xdata-xrefs.tsv").read_text())
            self.assertIn("A8=02, A5=06", (out / "u17-state-transitions.tsv").read_text())


if __name__ == "__main__":
    unittest.main()
