#!/usr/bin/env python3
import importlib.util
import tempfile
import unittest
from pathlib import Path
import hashlib

SPEC = importlib.util.spec_from_file_location("analyze_ds1230", Path(__file__).with_name("analyze_ds1230.py"))
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class DS1230Tests(unittest.TestCase):
    def test_tracked_canonical_identity(self):
        path = Path(__file__).parents[1] / "firmware/original/41.005.415.Z1-U17-DS1230Y-100.bin"
        data = path.read_bytes()
        self.assertEqual(len(data), MODULE.SIZE)
        self.assertEqual(hashlib.sha256(data).hexdigest(), "2e58841c485f9f805c159cee5901de053ca7397c20e5c08941328b6028152ca4")

    def test_checksum_and_fe_window(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "dump.bin"
            path.write_bytes(b"\x00" * MODULE.SIZE)
            result = MODULE.analyze(path)
        self.assertTrue(result["all_zero"])
        self.assertTrue(result["fe00_fef9_all_ff"] is False)
        self.assertFalse(result["signature_matches"])

    def test_decodes_fe_ljmp_table(self):
        data = bytearray(MODULE.SIZE)
        data[0x7E06:0x7E09] = bytes.fromhex("02 07 5D")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "trampoline.bin"
            path.write_bytes(data)
            result = MODULE.analyze(path)
        self.assertIn({"cpu_address": "0xFE06", "file_offset": "0x7E06", "target": "0x075D"}, result["fe_trampolines"])

    def test_rejects_wrong_size(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "short.bin"
            path.write_bytes(b"\xFF" * (MODULE.SIZE - 1))
            with self.assertRaises(ValueError):
                MODULE.analyze(path)


if __name__ == "__main__":
    unittest.main()
