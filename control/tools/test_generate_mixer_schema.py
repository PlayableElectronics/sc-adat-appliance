#!/usr/bin/env python3
"""Prove source-map edits flow through the runtime exporter into UI schema."""
import importlib.util
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MODULE_PATH = HERE / "generate_mixer_schema.py"
SPEC = importlib.util.spec_from_file_location("generate_mixer_schema", MODULE_PATH)
GENERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATOR)

class MixerSchemaTest(unittest.TestCase):
    def test_stereo_mapping_changes_generated_parameters(self):
        original = (ROOT / "payload/config/mixer.conf").read_text(encoding="utf-8")
        source_lines = {}
        other_lines = []
        for line in original.splitlines():
            if line.startswith("source.") and line.split(".", 2)[1].isdigit():
                number = int(line.split(".", 2)[1])
                source_lines.setdefault(number, []).append(line)
            else:
                other_lines.append(line)
        rewritten = []
        for line in other_lines:
            if line == "source.count=16": line = "source.count=15"
            if line == "channel.1.group=kick": line = "channel.1.group=drums"
            rewritten.append(line)
        first = [line.replace("source.1.mode=mono", "source.1.mode=stereo")
                 .replace("source.1.inputs=1", "source.1.inputs=1,2")
                 .replace("source.1.group=kick", "source.1.group=drums")
                 for line in source_lines[1]]
        rewritten.extend(first)
        for old_index in range(3, 17):
            new_index = old_index - 1
            rewritten.extend(line.replace(f"source.{old_index}.", f"source.{new_index}.", 1)
                              for line in source_lines[old_index])
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / "mixer.conf"
            config.write_text("\n".join(rewritten) + "\n", encoding="utf-8")
            schema = GENERATOR.build_schema(config)
        keys = {item["key"] for item in schema["controls"]}
        self.assertEqual(schema["sources"][0]["mode"], "stereo")
        self.assertEqual(schema["sources"][0]["inputs"], [1, 2])
        self.assertNotIn("source0Pan", keys)
        self.assertIn("source0Balance", keys)
        self.assertIn("source0Width", keys)
        self.assertEqual(len(schema["pages"]), 25)
        input_pages = [page for page in schema["pages"] if page["label"].startswith("INPUT ")]
        self.assertEqual(len(input_pages), 16)
        self.assertEqual(input_pages[0]["source_inputs"], [1, 2])
        self.assertEqual(input_pages[1]["source_inputs"], [1, 2])
        self.assertIn("source0Balance", input_pages[0]["controls"])
        self.assertNotIn("source0Balance", input_pages[1]["controls"])
        self.assertIn("input0Partner", input_pages[0]["controls"])
        self.assertIn("input1Partner", input_pages[1]["controls"])

if __name__ == "__main__":
    unittest.main()
