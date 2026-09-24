import json
import pathlib
import unittest


ROOT = pathlib.Path(__file__).parents[1]
PROJECT = ROOT / "control/chataigne/sc-adat-quad.noisette"
CONTROLS = ROOT / "control/chataigne/reference/controls.json"


class ChataigneProjectTests(unittest.TestCase):
    def test_seed_derived_project_and_version(self):
        project = json.loads(PROJECT.read_text())
        controls = json.loads(CONTROLS.read_text())
        self.assertEqual(project["metaData"]["version"], "1.10.4")
        self.assertEqual(project["modules"]["items"][0]["type"], "OSC")
        params = project["modules"]["items"][0]["params"]["containers"]["oscOutputs"]["items"][0]["parameters"]
        self.assertEqual(params[0], {"value": "192.168.1.100", "controlAddress": "/remoteHost"})
        self.assertEqual(params[1], {"value": 57120, "controlAddress": "/remotePort"})
        self.assertEqual(len(controls["groups"]), 8)
        self.assertEqual([g["name"] for g in controls["groups"]], ["kick", "drums", "bass", "music_a", "music_b", "vocals", "fx_a", "fx_b"])

    def test_contract_keys_are_not_hidden_or_guessed(self):
        controls = json.loads(CONTROLS.read_text())
        keys = {key for group in controls["groups"] for key in group["keys"]}
        self.assertIn("groupLevel0", keys)
        self.assertIn("group7SpatialBypass", keys)
        self.assertEqual(controls["osc"]["set"], {"address": "/mixer/set", "types": ",sf"})
        self.assertIn("groupNMute", controls["unsupported_placeholders"])


if __name__ == "__main__":
    unittest.main()
