#!/usr/bin/env python3
"""Contract-generation checks which require only the Python standard library."""

import importlib.util
import json
import re
import tempfile
import unittest
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GENERATOR_PATH = HERE / "tools" / "generate_norns_contract.py"
SPEC = importlib.util.spec_from_file_location("generate_norns_contract", GENERATOR_PATH)
GENERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATOR)


class GeneratorTest(unittest.TestCase):
    def setUp(self):
        self.contract = json.loads(
            (ROOT / "control" / "mixer-control-contract.json").read_text(encoding="utf-8")
        )

    def test_expected_safe_controls_and_unique_keys(self):
        controls, pages = GENERATOR.expanded_controls(self.contract)
        keys = [item["key"] for item in controls]
        self.assertEqual(len(keys), 105)
        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(keys[0], "master")
        self.assertEqual(keys[-1], "source15Pan")
        self.assertNotIn("trim0", keys)
        self.assertIn("source0Trim", keys)
        self.assertEqual(len(pages), 25)

    def test_stereo_source_uses_balance_and_width_instead_of_pan(self):
        sources = GENERATOR.source_map()
        sources[0] = {**sources[0], "mode": "stereo", "inputs": [1, 2]}
        sources.pop(1)
        controls, pages = GENERATOR.expanded_controls(self.contract, sources)
        keys = {item["key"] for item in controls}
        self.assertNotIn("source0Pan", keys)
        self.assertIn("source0Balance", keys)
        self.assertIn("source0Width", keys)
        self.assertEqual(pages[9]["label"], sources[0]["name"].upper())

    def test_every_generated_control_comes_from_writable_contract_entry(self):
        controls, _ = GENERATOR.expanded_controls(self.contract)
        definitions = self.contract["controls"] + self.contract["source_controls"]
        for control in controls:
            matches = []
            for definition in definitions:
                template = definition["key_template"]
                if "N" in template:
                    pattern = "^" + re.escape(template).replace("N", r"\d+") + "$"
                    match = re.match(pattern, control["key"]) is not None
                else:
                    match = control["key"] == template
                if match:
                    matches.append(definition)
            self.assertEqual(len(matches), 1, control["key"])
            self.assertTrue(matches[0].get("writable", True), control["key"])

    def test_checked_in_lua_is_reproducible(self):
        original = GENERATOR.OUTPUT_PATH
        with tempfile.TemporaryDirectory() as directory:
            generated = Path(directory) / "mixer_contract.lua"
            GENERATOR.OUTPUT_PATH = generated
            try:
                self.assertEqual(GENERATOR.generate(), 105)
            finally:
                GENERATOR.OUTPUT_PATH = original
            self.assertEqual(generated.read_bytes(), original.read_bytes())


if __name__ == "__main__":
    unittest.main()
