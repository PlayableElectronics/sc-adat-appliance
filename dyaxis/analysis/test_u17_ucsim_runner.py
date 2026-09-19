import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("u17_ucsim_runner", Path(__file__).with_name("u17_ucsim_runner.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class U17UcsimRunnerTests(unittest.TestCase):
    def test_intel_hex_records_have_valid_checksums(self):
        data = bytes(range(64))
        for line in module.ihex(data).splitlines()[:-1]:
            record = bytes.fromhex(line[1:])
            self.assertEqual(sum(record) & 0xFF, 0)

    def test_projection_preserves_known_candidate_contradiction(self):
        root = Path(__file__).parents[1]
        candidate = (root / "firmware/candidates/41.005.415.Z1-U17-first-app-SJMP-8000.bin").read_bytes()
        self.assertEqual(module.projected_path(candidate), "Checksum Good")

    def test_projection_of_original_and_zero_xdata_fails(self):
        root = Path(__file__).parents[1]
        original = (root / "firmware/original/41.005.415.Z1-U17-DS1230Y-100.bin").read_bytes()
        self.assertEqual(module.projected_path(original), "Checksum Failed")
        self.assertEqual(module.projected_path(bytes(module.SIZE)), "Checksum Failed")


if __name__ == "__main__":
    unittest.main()
