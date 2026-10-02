"""Static contract checks; audio behavior still needs the scsynth acceptance run."""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SYNTHDEFS = (ROOT / "supercollider/synthdefs/sc-adat-mixer.scd").read_text()
CONTRACT = json.loads((ROOT / "control/mixer-control-contract.json").read_text())


class StereoDspContractTests(unittest.TestCase):
    def test_quad_group_definition_is_unchanged_and_stereo_is_separate(self):
        quad = SYNTHDEFS.split("SynthDef(\\sc_adat_group", 1)[1].split("SynthDef(\\sc_adat_stereo_group", 1)[0]
        self.assertNotIn("Compander", quad)
        self.assertNotIn("BLowShelf", quad)
        self.assertNotIn("duckAmountDb", quad)
        self.assertIn("SynthDef(\\sc_adat_stereo_group", SYNTHDEFS)

    def test_neutral_and_bypass_controls_match_authoritative_defaults(self):
        definitions = {item["key_template"]: item for item in CONTRACT["controls"]}
        for key in ("groupNEqBypass", "groupNCompBypass", "groupNSatBypass"):
            self.assertEqual(definitions[key]["default"], 1)
            self.assertEqual(definitions[key]["modes"], ["stereo"])
        self.assertEqual(definitions["groupNDuckAmountDb"]["default"], 0)
        self.assertEqual(definitions["masterEqBypass"]["default"], 1)

    def test_ducker_is_bounded_non_amplifying_and_uses_raw_kick_stem(self):
        self.assertIn("detector = In.ar(52, 2).sum * 0.5", SYNTHDEFS)
        self.assertIn("duckAmountDb.clip(0, 18)", SYNTHDEFS)
        self.assertIn("10 ** (0 - duckAmountDb.clip(0, 18) / 20)", SYNTHDEFS)
        self.assertIn("duckGain = LagUD.kr", SYNTHDEFS)
        self.assertIn("real kick-duck audio flow", (ROOT / "mixer/test_stereo.py").read_text())

    def test_master_limiter_and_panic_mute_follow_stereo_eq(self):
        master = SYNTHDEFS.split("SynthDef(\\sc_adat_stereo_master", 1)[1]
        self.assertIn("BPeakEQ.ar(x,1000,0.5,eqDb.clip(-6,6))", master)
        self.assertIn("Limiter.ar((shaped * master).clip2(4), 0.99, 0.01) * (1-panicMute.clip(0,1))", master)

    def test_test_generator_has_cap_timeout_and_group_selection(self):
        generator = SYNTHDEFS.split("SynthDef(\\sc_adat_test_generator", 1)[1].split("SynthDef(\\sc_adat_quad_master", 1)[0]
        self.assertIn("level.clip(0,0.031623)", generator)
        self.assertIn("timeout.clip(1,30)", generator)
        self.assertIn("InRange.kr(destination,g-0.01,g+0.01)", generator)


if __name__ == "__main__":
    unittest.main()
