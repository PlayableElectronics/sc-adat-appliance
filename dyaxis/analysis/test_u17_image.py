import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("u17_image", Path(__file__).with_name("u17_image.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class U17ImageTests(unittest.TestCase):
    def test_tracked_first_sjmp_candidate_properties_independently(self):
        root = Path(__file__).parents[1]
        candidate = (root / "firmware/candidates/41.005.415.Z1-U17-first-app-SJMP-8000.bin").read_bytes()
        original = (root / "firmware/original/41.005.415.Z1-U17-DS1230Y-100.bin").read_bytes()
        self.assertEqual(len(candidate), 32768)
        self.assertEqual(candidate[:2], bytes.fromhex("80 FE"))
        self.assertEqual(candidate[2:0x7DFC], bytes(0x7DFC - 2))
        self.assertEqual(candidate[0x7DFC:0x7DFE], bytes.fromhex("AA 55"))
        expected = (~(sum(candidate[:0x7DFD]) & 0xFFFF)) & 0xFFFF
        self.assertEqual(int.from_bytes(candidate[0x7DFE:0x7E00], "big"), expected)
        self.assertEqual(candidate[0x7E00:], original[0x7E00:])
        self.assertEqual(candidate[0x7E00:] != original[0x7E00:], False)

    def test_build_and_validate(self):
        template = bytes(range(256)) * 128
        image = mod.build(b"test application", template)
        self.assertEqual(mod.validate(image), [])
        self.assertEqual(image[mod.TRAMPOLINE_OFFSET:], template[mod.TRAMPOLINE_OFFSET:])
        self.assertEqual(image[mod.SIGNATURE_OFFSET:mod.SIGNATURE_OFFSET + 2], b"\xAA\x55")

    def test_rejects_corruption_and_overlap(self):
        template = bytes([0x5A]) * mod.IMAGE_SIZE
        image = bytearray(mod.build(b"x", template))
        image[0] ^= 1
        self.assertTrue(mod.validate(bytes(image)))
        with self.assertRaises(ValueError):
            mod.build(bytes(mod.PAYLOAD_MAX + 1), template)

    def test_checksum_includes_signature_first_byte(self):
        image = bytearray(mod.IMAGE_SIZE)
        image[mod.SIGNATURE_OFFSET:mod.SIGNATURE_OFFSET + 2] = b"\xAA\x55"
        self.assertEqual(mod.checksum(bytes(image)), 0xFF55)
        image[mod.CHECKSUM_OFFSET:mod.CHECKSUM_OFFSET + 2] = mod.checksum(image).to_bytes(2, "big")
        self.assertEqual(mod.validate(bytes(image)), [])

    def test_checksum_boundary_mutations(self):
        image = bytearray(mod.IMAGE_SIZE)
        image[mod.SIGNATURE_OFFSET:mod.SIGNATURE_OFFSET + 2] = b"\xAA\x55"
        baseline = mod.checksum(bytes(image))
        changed_first_signature = bytearray(image)
        changed_first_signature[0x7DFC] ^= 1
        self.assertNotEqual(mod.checksum(bytes(changed_first_signature)), baseline)
        changed_second_signature = bytearray(image)
        changed_second_signature[0x7DFD] ^= 1
        self.assertEqual(mod.checksum(bytes(changed_second_signature)), baseline)
        for offset in (0x7DFE, 0x7DFF):
            changed_checksum = bytearray(image)
            changed_checksum[offset] ^= 1
            self.assertEqual(mod.checksum(bytes(changed_checksum)), baseline)


if __name__ == "__main__":
    unittest.main()
