import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("u17_checksum_emulator", Path(__file__).with_name("u17_checksum_emulator.py"))
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class U17ChecksumEmulatorTests(unittest.TestCase):
    def test_candidate_falsifies_linear_xdata_hypothesis(self):
        path = Path(__file__).parents[1] / "firmware/candidates/41.005.415.Z1-U17-first-app-SJMP-8000.bin"
        result = module.analyze(path)
        self.assertEqual(result["marker_branch"], "0x029C -> 0x02A1 -> 0x02CD")
        self.assertEqual(result["marker_fdfE_fdff"]["bytes"], "FDD7")
        self.assertFalse(result["marker_fdfE_fdff"]["matches_AA55"])
        self.assertEqual(result["checksum"]["read_count"], 0x7DFD)
        self.assertEqual(result["checksum"]["result_r6_r7"], "0xFDD7")
        self.assertTrue(result["stored_checksum_matches"])
        self.assertTrue(result["low_byte_matches"])
        self.assertTrue(result["high_byte_matches"])
        self.assertEqual(result["final_path"], "Checksum Good")
        self.assertEqual(result["branch"], "0x029C -> 0x02A1 -> 0x02CD -> 0x02FD")
        # The physical console displayed failure.  Therefore this complete
        # linear-XDATA prediction is a falsification of that mapping
        # hypothesis, not an explanation of the display.
        self.assertNotEqual(result["final_path"], "Checksum Failed")

    def test_checksum_mismatch_reaches_failure_display(self):
        image = bytearray(module.IMAGE_SIZE)
        image[0x7DFE:0x7E00] = b"\x00\x00"
        result = module.startup_validation(bytes(image))
        self.assertFalse(result["low_byte_matches"])
        self.assertEqual(result["final_path"], "Checksum Failed")
        self.assertIn("0x02EB -> 0x0311", result["branch"])

    def test_checksum_known_answer_is_instruction_accurate(self):
        image = bytearray(module.IMAGE_SIZE)
        image[0x7DFC] = 0xAA
        image[0x7DFD] = 0x55
        result = module.checksum_037c(bytes(image))
        self.assertEqual(result["end_exclusive_cpu"], "0xFDFD")
        self.assertEqual(result["read_count"], 0x7DFD)
        self.assertEqual(result["reads"][0]["cpu_address"], "0x8000")
        self.assertEqual(result["reads"][-1]["cpu_address"], "0xFDFC")
        self.assertEqual(result["result_r6_r7"], "0xFF55")


if __name__ == "__main__":
    unittest.main()
