#!/usr/bin/env python3
import struct
import tempfile
import unittest
from pathlib import Path

from u17_host_tool import CANDIDATES, CaptureWriter, MAGIC, decode_capture, parse_hex, simulate_service_byte


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

    def test_service_state_simulation_matches_rom_dispatch(self):
        event, state, count = simulate_service_byte(0, 0x02)
        self.assertEqual((state, event["action"]), (1, "arm 017B/017A; advance"))
        event, state, count = simulate_service_byte(state, 0x06)
        self.assertEqual((state, count), (2, 6))
        event, state, count = simulate_service_byte(state, 0x06, count)
        self.assertEqual((state, count), (0x28, 6))
        event, state, count = simulate_service_byte(state, 0x03, count)
        self.assertEqual((state, count), (0x29, 5))

    def test_decode_mode_is_read_only_and_preserves_raw_records(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.u17cap"
            writer = CaptureWriter(path)
            writer.write("RX", b"\x02\x06\x06\x03", timestamp_ns=123)
            writer.close()
            report = decode_capture(path)
        self.assertEqual(report["rx_byte_count"], 4)
        self.assertEqual(report["records"][0]["hex"], "02060603")
        self.assertIn("not proven", report["interpretation"])


if __name__ == "__main__":
    unittest.main()
