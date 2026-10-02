"""Exercise the production segment writer with deterministic 19-channel PCM."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest
import wave

ROOT = Path(__file__).resolve().parents[1]


class RecorderSegmentIntegrationTests(unittest.TestCase):
    def test_crossing_blocks_reassemble_sample_for_sample(self):
        pkg = subprocess.check_output(["pkg-config", "--cflags", "--libs", "jack", "sndfile"], text=True)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = root / "recorder-segment-fixture"
            flags = shlex.split(pkg)
            cflags = [flag for flag in flags if flag.startswith(("-I", "-D", "-pthread"))]
            libraries = [flag for flag in flags if flag.startswith(("-L", "-l"))]
            compile_command = [os.environ.get("CC", "cc"), "-std=c11", "-Wall", "-Wextra", "-Werror",
                               "-Wno-unused-function", *cflags, str(ROOT / "scripts/test-support/recorder-segment-fixture.c"),
                               "-pthread", *libraries, "-o", str(executable)]
            subprocess.run(compile_command, check=True, cwd=ROOT)
            session = root / "session"
            reference_root = root / "expected"
            reference_root.mkdir()
            subprocess.run([str(executable), str(session), str(reference_root)], check=True)

            observed_counts = []
            reconstructed = {channel: bytearray() for channel in range(1, 20)}
            for index, expected_frames in enumerate((10, 10, 10, 7)):
                segment = session / f"segment-{index:03d}"
                metadata = json.loads((segment / "segment.json").read_text())
                self.assertEqual(metadata, {"segment_index": index, "start_frame": index * 10,
                                            "frame_count": expected_frames, "sample_rate": 48000,
                                            "finalized": True})
                observed_counts.append(metadata["frame_count"])
                for channel in range(1, 20):
                    name = f"channel_{channel:02d}.wav"
                    with wave.open(str(segment / name), "rb") as stream:
                        self.assertEqual((stream.getnchannels(), stream.getsampwidth(), stream.getframerate()), (1, 3, 48000))
                        self.assertEqual(stream.getnframes(), expected_frames)
                        segment_pcm = stream.readframes(expected_frames)
                    reconstructed[channel].extend(segment_pcm)
                    if index == 3:
                        with wave.open(str(reference_root / "reference" / name), "rb") as reference:
                            self.assertEqual(reference.getnframes(), 37)
                            reference_pcm = reference.readframes(37)
                        self.assertEqual(bytes(reconstructed[channel]), reference_pcm,
                                         f"PCM-24 mismatch after reassembling {name}")
            self.assertEqual(observed_counts, [10, 10, 10, 7])
            self.assertEqual(sum(observed_counts), 37)


if __name__ == "__main__":
    unittest.main()
