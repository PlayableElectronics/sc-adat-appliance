import struct
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))
import nano_edge_capture as nec

def make_capture(baud=9600, invert=False, jitter=0, truncated=False, overflow=0):
    timer_hz, bit = 2_000_000, 2_000_000 / baud
    level, edges, tick = 1 ^ int(invert), [], 0
    def add(new_level, at):
        nonlocal level
        if new_level != level: edges.append((int(at), new_level)); level = new_level
    for value in (0x55, 0xA5, 0x00):
        add(0 ^ int(invert), tick)
        for index in range(8):
            tick += bit; add(((value >> index) & 1) ^ int(invert), tick + (jitter if index % 2 else 0))
        tick += bit; add(1 ^ int(invert), tick)
        tick += bit
    raw = bytearray(b"DYAXEDG1") + bytes((1, nec.FRAME_HEADER))
    raw += struct.pack("<I", timer_hz) + bytes((1 ^ int(invert), 0)) + struct.pack("<H", 96)
    raw += bytes((nec.FRAME_START,)) + struct.pack("<I", 0) + bytes((1 ^ int(invert),))
    previous = 0
    for edge_tick, edge_level in edges:
        raw += bytes((nec.FRAME_EDGE,)) + struct.pack("<I", edge_tick - previous) + bytes((edge_level,)); previous = edge_tick
    if overflow: raw += bytes((nec.FRAME_OVERFLOW,)) + struct.pack("<II", overflow, overflow)
    raw += bytes((nec.FRAME_STOP,)) + struct.pack("<II", int(tick), overflow)
    return bytes(raw[:-2] if truncated else raw)

class NanoEdgeCaptureTests(unittest.TestCase):
    def test_jitter_and_inverted_polarity_rank_a_decode(self):
        ranked = nec.rank_decodes(nec.parse_capture(make_capture(invert=True, jitter=1)))
        self.assertTrue(any(result["invert"] for result in ranked))
        self.assertTrue(any(item["byte"] == 0x55 for result in ranked
                            if result["invert"] for item in result["bytes"]))

    def test_truncated_capture_is_rejected(self):
        with self.assertRaises((ValueError, struct.error)): nec.parse_capture(make_capture(truncated=True))

    def test_overflow_is_preserved_and_reported(self):
        capture = nec.parse_capture(make_capture(overflow=7))
        self.assertEqual(capture.overflow, 7); self.assertTrue(capture.stopped)

    def test_fixture_generation_is_deterministic_and_raw_is_preserved(self):
        first = make_capture(baud=10416.6667); self.assertEqual(first, make_capture(baud=10416.6667))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "fixture.dyaxedge"; path.write_bytes(first); self.assertEqual(path.read_bytes(), first)

    def test_ready_prefix_is_ignored_without_losing_raw_bytes(self):
        raw = bytes((nec.FRAME_READY,)) + make_capture()
        capture = nec.parse_capture(raw)
        self.assertEqual(capture.raw, raw)
        self.assertTrue(capture.stopped)

if __name__ == "__main__": unittest.main()
