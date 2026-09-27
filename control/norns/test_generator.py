#!/usr/bin/env python3
"""Checks for the schema-driven Norns renderer."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GENERATOR_PATH = HERE / "tools/generate_norns_contract.py"
SPEC = importlib.util.spec_from_file_location("generate_norns_contract", GENERATOR_PATH)
GENERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATOR)

class GeneratorTest(unittest.TestCase):
    def setUp(self):
        self.schema = json.loads((ROOT / "control/generated/mixer-schema.json").read_text(encoding="utf-8"))

    def test_expected_controls_and_unique_keys(self):
        controls = [GENERATOR.norns_control(item) for item in self.schema["controls"]]
        keys = [item["key"] for item in controls]
        self.assertEqual(len(keys), 105)
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(keys[0], "master")
        self.assertEqual(keys[-1], "source15Pan")
        self.assertNotIn("trim0", keys)
        self.assertIn("source0Trim", keys)
        self.assertEqual(len(self.schema["pages"]), 25)

    def test_schema_contains_complete_runtime_model(self):
        self.assertEqual(len(self.schema["groups"]), 8)
        self.assertEqual(len(self.schema["sources"]), 16)
        self.assertEqual({value for source in self.schema["sources"] for value in source["inputs"]}, set(range(1, 17)))
        for control in self.schema["controls"]:
            self.assertIn("value_type", control)
            self.assertIn("range", control)
            self.assertIn("default", control)

    def test_checked_in_lua_is_reproducible(self):
        with tempfile.TemporaryDirectory() as directory:
            generated = Path(directory) / "mixer_contract.lua"
            self.assertEqual(GENERATOR.generate(output_path=generated), 105)
            self.assertEqual(generated.read_bytes(), GENERATOR.OUTPUT_PATH.read_bytes())

if __name__ == "__main__":
    unittest.main()
