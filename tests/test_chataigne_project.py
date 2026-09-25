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
        self.assertEqual(len(project["dashboardManager"]["items"]), 3)
        self.assertEqual(len(project["dashboardManager"]["items"][0]["itemManager"]["items"]), 8)
        self.assertEqual(project["modules"]["items"][0]["scripts"]["items"][0]["parameters"][0]["value"], "scripts/sc_adat_mixer.js")

    def test_contract_keys_are_not_hidden_or_guessed(self):
        controls = json.loads(CONTROLS.read_text())
        keys = {key for group in controls["groups"] for key in group["keys"]}
        self.assertIn("groupLevel0", keys)
        self.assertIn("group7SpatialBypass", keys)
        self.assertEqual(controls["osc"]["set"], {"address": "/mixer/set", "types": ",sf"})
        self.assertIn("groupNMute", controls["unsupported_placeholders"])
        output_params = json.loads(PROJECT.read_text())["modules"]["items"][0]["params"]["containers"]["oscOutputs"]["items"][0]["parameters"]
        self.assertFalse(any("routingMode" in item.get("controlAddress", "") for item in output_params))

    def test_native_targets_are_persisted(self):
        project = json.loads(PROJECT.read_text())
        group_names = [item["niceName"] for item in project["dashboardManager"]["items"][0]["itemManager"]["items"]]
        self.assertEqual(group_names, [f"{name} ({i})" for i, name in enumerate(("kick", "drums", "bass", "music_a", "music_b", "vocals", "fx_a", "fx_b"))])
        for dashboard in project["dashboardManager"]["items"]:
            for item in dashboard["itemManager"]["items"]:
                if item["type"] == "DashboardGroupItem":
                    self.assertEqual(len(item["itemManager"]["items"]), 5)
                else:
                    self.assertIn("controllable", item)
        script = (ROOT / "control/chataigne/scripts/sc_adat_mixer.js").read_text()
        self.assertIn("root.getChild(\"customVariables\")", script)
        self.assertIn("getChild(\"stopAll\")", script)


if __name__ == "__main__":
    unittest.main()
