import math
import unittest

from tools.chataigne_mock_osc import GROUP_KEYS, MockMixer, packet, parse


class ChataigneMockTests(unittest.TestCase):
    def test_round_trip_and_all_group_keys(self):
        mixer = MockMixer()
        for i in range(8):
            self.assertEqual(mixer.handle(packet("/mixer/set", "sf", [f"groupLevel{i}", i / 8]))[:8], packet("/mixer/ok", "s", [f"groupLevel{i}"])[:8])
        self.assertEqual(set(GROUP_KEYS), {k for k in mixer.state if k in GROUP_KEYS})

    def test_refresh_and_state_reply(self):
        mixer = MockMixer()
        self.assertEqual(parse(mixer.handle(packet("/mixer/get-all"))), ("/mixer/get-all-done", ",", []))
        self.assertGreaterEqual(len(mixer.sent), len(GROUP_KEYS))

    def test_malformed_and_unsupported(self):
        mixer = MockMixer()
        path, types, args = parse(mixer.handle(b"not osc"))
        self.assertEqual((path, types), ("/mixer/error", ",s"))
        path, _, args = parse(mixer.handle(packet("/mixer/set", "sf", ["routingMode", 1])))
        self.assertEqual(path, "/mixer/error")
        self.assertTrue(mixer.errors)

    def test_values_are_finite(self):
        mixer = MockMixer()
        path, _, _ = parse(mixer.handle(packet("/mixer/set", "sf", ["groupLevel0", math.inf])))
        self.assertEqual(path, "/mixer/error")


if __name__ == "__main__":
    unittest.main()
