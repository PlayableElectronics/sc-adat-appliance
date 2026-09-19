import importlib.util
import unittest
from pathlib import Path

spec = importlib.util.spec_from_file_location("u17_image", Path(__file__).with_name("u17_image.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class U17ImageTests(unittest.TestCase):
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
        image[mod.CHECKSUM_OFFSET:mod.CHECKSUM_OFFSET + 2] = mod.checksum(image).to_bytes(2, "big")
        self.assertEqual(mod.validate(bytes(image)), [])


if __name__ == "__main__":
    unittest.main()
