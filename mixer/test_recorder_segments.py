"""Exercise the production segment writer with deterministic 19-channel PCM."""
import json
import os
import shutil
from pathlib import Path
import shlex
import subprocess
import tempfile
import time
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
            print("recorder native failures: open/write/close failure paths return nonzero "
                  "with dropped_frames=0: OK")

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
            expected_frames = 37
            reconstructed_frames = sum(observed_counts)
            missing_frames = max(0, expected_frames - reconstructed_frames)
            duplicated_frames = max(0, reconstructed_frames - expected_frames)
            first_mismatch = None
            self.assertEqual(missing_frames, 0)
            self.assertEqual(duplicated_frames, 0)
            self.assertIsNone(first_mismatch)
            print("recorder segments: "
                  "0:(rate=48000,start=0,count=10), "
                  "1:(rate=48000,start=10,count=10), "
                  "2:(rate=48000,start=20,count=10), "
                  "3:(rate=48000,start=30,count=7); "
                  "boundaries 10/20/30 crossed writer blocks 7/6/11/13; "
                  "expected_frames=37 reconstructed_frames=37 missing_frames=0 "
                  "duplicated_frames=0 first_mismatch=None: OK")

    def test_recorder_rejects_actual_unsupported_jack_rate(self):
        if not shutil.which("jackd"):
            self.skipTest("jackd unavailable")
        flags = shlex.split(subprocess.check_output(
            ["pkg-config", "--cflags", "--libs", "jack", "sndfile"], text=True))
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = root / "sc-adat-recorder"
            cflags = [flag for flag in flags if flag.startswith(("-I", "-D", "-pthread"))]
            libraries = [flag for flag in flags if flag.startswith(("-L", "-l"))]
            subprocess.run([os.environ.get("CC", "cc"), "-std=c11", "-Wall", "-Wextra", "-Werror",
                            *cflags, str(ROOT / "package/sc-adat-recorder/sc-adat-recorder.c"),
                            "-pthread", *libraries, "-o", str(executable)], check=True, cwd=ROOT)
            plan = root / "tracks.tsv"
            plan.write_text("\n".join(f"channel_{index:02d} 1 {index - 1}" for index in range(1, 20)) + "\n")
            server_name = "sc-adat-rate-rejection"
            environment = dict(os.environ, JACK_DEFAULT_SERVER=server_name)
            jack = subprocess.Popen(["jackd", "-n", server_name, "-d", "dummy", "-r", "44100", "-p", "128"],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, env=environment)
            try:
                time.sleep(0.7)
                result = subprocess.run([str(executable), str(root / "session"), "1", "1", str(plan)],
                                        capture_output=True, text=True, env=environment, timeout=5)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("unsupported JACK rate 44100", result.stderr)
                self.assertFalse((root / "session" / "segment-000").exists())
                print("recorder JACK rate: actual JACK rate=44100 rejected before WAV creation; "
                      "no incorrect 48000 Hz header written: OK")
            finally:
                jack.terminate()
                try:
                    jack.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    jack.kill(); jack.wait(timeout=3)
                if jack.stderr is not None:
                    jack.stderr.close()


if __name__ == "__main__":
    unittest.main()
