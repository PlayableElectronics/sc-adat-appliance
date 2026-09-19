import hashlib
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]
CANDIDATE = (ROOT / "firmware/candidates/41.005.415.Z1-U17-first-app-SJMP-8000.bin").read_bytes()
ORIGINAL = (ROOT / "firmware/original/41.005.415.Z1-U17-DS1230Y-100.bin").read_bytes()


class DS1230RetentionTests(unittest.TestCase):
    def test_reference_hashes_and_expected_candidate_delta(self):
        self.assertEqual(hashlib.sha256(CANDIDATE).hexdigest(), "cb5a4306ce73bef3b6ec76b18b367606d1a954e99d6584350c6b7ef394c9ee19")
        self.assertEqual(hashlib.sha256(ORIGINAL).hexdigest(), "2e58841c485f9f805c159cee5901de053ca7397c20e5c08941328b6028152ca4")
        offsets = [i for i, (a, b) in enumerate(zip(CANDIDATE, ORIGINAL)) if a != b]
        self.assertEqual(offsets, [0, 1, 0x7DFC, 0x7DFD, 0x7DFE, 0x7DFF])

    def test_clear_03a4_span_is_distinct_from_protected_region(self):
        self.assertEqual(CANDIDATE[2:0x7DFC], bytes(0x7DFC - 2))
        self.assertNotEqual(CANDIDATE[0:2], bytes(2))
        self.assertNotEqual(CANDIDATE[0x7DFC:0x7E00], bytes(4))
        self.assertEqual(CANDIDATE[0x7E00:], ORIGINAL[0x7E00:])


if __name__ == "__main__":
    unittest.main()
