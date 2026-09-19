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
        result = MODULE.analyze(path)
        self.assertEqual(result["fe_trampoline_count"], 43)
        self.assertEqual(result["checksum_sum_16bit"], "0x0000")
        self.assertEqual(result["stored_checksum"], "0x0000")

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
        entry = next(x for x in result["fe_trampolines"] if x["cpu_address"] == "0xFE06")
        self.assertEqual((entry["file_offset"], entry["target"]), ("0x7E06", "0x075D"))
        self.assertEqual(entry["likely_function"], "display/string service")

    def test_rejects_wrong_size(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "short.bin"
            path.write_bytes(b"\xFF" * (MODULE.SIZE - 1))
            with self.assertRaises(ValueError):
                MODULE.analyze(path)

    def test_nonzero_inventory_keeps_post_fe_data_separate(self):
        data = bytearray(MODULE.SIZE)
        data[0x7E00:0x7E03] = bytes.fromhex("02 12 34")
        data[0x7F00] = 0xA5
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "regions.bin"
            path.write_bytes(data)
            regions = MODULE.analyze(path)["nonzero_regions"]
        self.assertEqual(regions[0]["classification"], "CODE trampoline table")
        self.assertEqual(regions[-1]["classification"], "unexplained retained/residual data")


if __name__ == "__main__":
    unittest.main()
