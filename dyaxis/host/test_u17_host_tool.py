#!/usr/bin/env python3
import struct
import tempfile
import unittest
from pathlib import Path

from u17_host_tool import CANDIDATES, CaptureWriter, MAGIC, parse_hex


class U17HostToolTests(unittest.TestCase):
    def test_parse_hex(self):
        self.assertEqual(parse_hex("01 02:fe-ff"), b"\x01\x02\xfe\xff")

    def test_capture_preserves_timestamped_binary_records(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.u17cap"
            writer = CaptureWriter(path)
            writer.write("RX", b"\x10\xfe", timestamp_ns=123)
            writer.write("TX", b"\x02", timestamp_ns=456)
            writer.close()
            raw = path.read_bytes()
        self.assertTrue(raw.startswith(MAGIC))
        first = struct.unpack(">QBI", raw[len(MAGIC):len(MAGIC) + 13])
        self.assertEqual(first, (123, 0, 2))
        offset = len(MAGIC) + 13 + 2
        second = struct.unpack(">QBI", raw[offset:offset + 13])
        self.assertEqual(second, (456, 1, 1))
        self.assertEqual(raw[offset + 13:], b"\x02")

    def test_current_candidates_are_nontransmittable_until_wire_bytes_are_known(self):
        self.assertTrue(CANDIDATES)
        self.assertTrue(all(item.wire_hex is None for item in CANDIDATES.values()))


if __name__ == "__main__":
    unittest.main()
