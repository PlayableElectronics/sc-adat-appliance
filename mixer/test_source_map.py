#!/usr/bin/env python3
import copy
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))
from contract import source_contract
from mixerctl import configured_sources, read_config, source_contract_for, source_map_snapshot
from source_map import (AtomicSourceMap, SourceMapError, mono_pan_gains,
                        stereo_balance_width, validate_source_map)

GROUPS = ("kick", "drums", "bass", "music_a", "music_b", "vocals", "fx_a", "fx_b")


def mono_entries():
    return [{"id": f"input_{i}", "name": f"Input {i}", "mode": "mono", "inputs": [i],
             "group": GROUPS[(i - 1) % len(GROUPS)]} for i in range(1, 17)]


class SourceMapTests(unittest.TestCase):
    def test_valid_all_mono_map(self):
        sources = validate_source_map(mono_entries(), GROUPS)
        self.assertEqual(tuple(source.inputs[0] for source in sources), tuple(range(1, 17)))

    def test_valid_mixed_map_covers_every_input(self):
        entries = [{"id": "drums", "name": "Drums", "mode": "stereo", "inputs": [1, 2], "group": "drums"}]
        entries += [{"id": f"input_{i}", "name": f"Input {i}", "mode": "mono", "inputs": [i],
                     "group": GROUPS[(i - 1) % len(GROUPS)]} for i in range(3, 17)]
        self.assertEqual(sum(len(source.inputs) for source in validate_source_map(entries, GROUPS)), 16)

    def assert_invalid(self, entries, text):
        with self.assertRaisesRegex(SourceMapError, text):
            validate_source_map(entries, GROUPS)

    def test_map_rejects_missing_duplicate_and_bad_shapes(self):
        entries = mono_entries()
        self.assert_invalid(entries[:-1], "missing inputs")
        duplicate = copy.deepcopy(entries); duplicate[-1]["inputs"] = [15]
        self.assert_invalid(duplicate, "duplicate inputs")
        malformed = copy.deepcopy(entries); malformed[0]["inputs"] = [1, 2]
        self.assert_invalid(malformed, "mono requires")
        malformed = copy.deepcopy(entries); malformed[0]["mode"] = "stereo"
        self.assert_invalid(malformed, "stereo requires")

    def test_map_rejects_identity_and_group_errors(self):
        entries = mono_entries(); entries[1]["id"] = entries[0]["id"]
        self.assert_invalid(entries, "duplicate source ID")
        entries = mono_entries(); entries[0]["group"] = "not_a_group"
        self.assert_invalid(entries, "nonexistent group")
        entries = mono_entries(); entries[0]["extra"] = True
        self.assert_invalid(entries, "unknown fields")

    def test_stereo_order_is_preserved_and_updates_are_atomic(self):
        entries = [{"id": "pair", "name": "Pair", "mode": "stereo", "inputs": [2, 1], "group": "kick"}]
        entries += [{"id": f"input_{i}", "name": f"Input {i}", "mode": "mono", "inputs": [i], "group": "drums"} for i in range(3, 17)]
        state = AtomicSourceMap(entries, GROUPS)
        before = state.snapshot()
        invalid = copy.deepcopy(entries); invalid[0]["inputs"] = [1]
        with self.assertRaises(SourceMapError): state.replace(invalid)
        self.assertEqual(state.snapshot(), before)
        self.assertEqual(state.sources[0].inputs, (2, 1))

    def test_default_map_is_backward_compatible(self):
        values, channels = read_config(os.path.join(os.path.dirname(__file__), "..", "payload/config/mixer.conf"))
        sources = configured_sources(values)
        self.assertEqual(len(sources), 16)
        self.assertTrue(all(source.mode == "mono" for source in sources))
        self.assertEqual([source.inputs[0] for source in sources], list(range(1, 17)))
        self.assertEqual([source.group for source in sources], [row["group"] for row in channels])

    def test_contract_and_serializable_snapshot(self):
        values, channels = read_config(os.path.join(os.path.dirname(__file__), "..", "payload/config/mixer.conf"))
        contract = source_contract_for(values)
        self.assertEqual(contract["contract_version"], "1.1.0")
        self.assertEqual({item["mode"] for item in contract["sources"]}, {"mono"})
        self.assertIn("source0Pan", {control["key"] for control in contract["sources"][0]["controls"]})
        snapshot = source_map_snapshot(values)
        json.dumps(snapshot)
        self.assertEqual(snapshot["sources"][0]["inputs"], [1])

    def test_mono_pan_stereo_orientation_linked_controls_balance_width(self):
        self.assertEqual(mono_pan_gains(-1), (1.0, 0.0))
        self.assertEqual(mono_pan_gains(1), (0.0, 1.0))
        self.assertEqual(stereo_balance_width(1.0, 0.0, 0, 1)[1], 0.0)
        self.assertAlmostEqual(stereo_balance_width(1.0, 0.0, 0, 1)[0], 1.0)
        self.assertEqual([round(value, 12) for value in stereo_balance_width(1.0, 0.0, 0, 0)], [0.5, 0.5])
        self.assertAlmostEqual(stereo_balance_width(1.0, 0.0, -1, 1)[0], 2 ** 0.5)
        self.assertEqual(stereo_balance_width(1.0, 0.0, -1, 1)[1], 0.0)
        self.assertEqual(stereo_balance_width(1.0, 0.0, 1, 1), (0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
