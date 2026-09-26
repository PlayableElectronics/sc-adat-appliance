#!/usr/bin/env python3
"""Mock-OSC tests for the development-only terminal console."""
import socket
import threading
import unittest
from pathlib import Path

from console import ConsoleModel, METER_PERIOD, OscClient, db
from mixerctl import METER_WIDTH, controls, packet, parse_packet, read_config


class MockMixer:
    def __init__(self):
        values, channels = read_config("../payload/config/mixer.conf")
        self.state = dict(controls(values, channels))
        self.requests = []
        self.reject = False
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(0.1)
        self.port = self.sock.getsockname()[1]
        self.stop = False
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def close(self):
        self.stop = True
        self.sock.close()
        self.thread.join(timeout=1)

    def run(self):
        while not self.stop:
            try:
                data, address = self.sock.recvfrom(65535)
            except (OSError, socket.timeout):
                continue
            path, _, values = parse_packet(data)
            self.requests.append((path, values))
            if path == "/mixer/get-all":
                for key, value in self.state.items():
                    types = ",ss" if isinstance(value, str) else ",sf"
                    self.sock.sendto(packet("/mixer/state", types, [key, value]), address)
                self.sock.sendto(packet("/mixer/get-all-done", ",i", [len(self.state)]), address)
            elif path == "/mixer/meters":
                self.sock.sendto(packet("/mixer/meters", "," + "f" * METER_WIDTH, [0.0] * METER_WIDTH), address)
            elif path == "/mixer/get":
                key = values[0]
                self.sock.sendto(packet("/mixer/state", ",sf", [key, self.state[key]]), address)
            elif path == "/mixer/set":
                key, value = values
                if self.reject:
                    self.sock.sendto(packet("/mixer/error", ",s", ["mock rejection"]), address)
                else:
                    self.state[key] = value
                    self.sock.sendto(packet("/mixer/ok", ",s", [key]), address)


class ConsoleTests(unittest.TestCase):
    def setUp(self):
        self.mock = MockMixer()
        self.model = ConsoleModel(OscClient(port=self.mock.port), health_reader=lambda: {"ok": True})

    def tearDown(self):
        self.mock.close()
        self.model.client.close()

    def test_start_gets_state_without_writing(self):
        self.model.start()
        self.assertEqual(self.mock.requests[0][0], "/mixer/get-all")
        self.assertNotIn("/mixer/set", [path for path, _ in self.mock.requests])

    def test_conversion_ranges_and_readback(self):
        self.model.start()
        self.assertEqual(db(1.0), "+0.0")
        self.assertTrue(self.model.write("trim0", -6.0))
        self.assertAlmostEqual(self.mock.state["trim0"], 10 ** (-6 / 20), places=5)
        with self.assertRaises(ValueError):
            self.model.write("group0PosX", 0.6)
        with self.assertRaises(ValueError):
            self.model.write("group0PosY", 0.6)
        with self.assertRaises(ValueError):
            self.model.write("master", float("nan"))

    def test_ack_readback_and_error(self):
        self.model.start()
        self.assertTrue(self.model.write("master", 0.251188636))
        self.assertAlmostEqual(self.model.state["master"], 0.251188636, places=6)
        self.mock.reject = True
        self.assertFalse(self.model.write("mute0", 1))
        self.assertIn("mock rejection", self.model.message)

    def test_master_increase_requires_confirmation_and_small_steps(self):
        self.model.start()
        self.model.write("master", 0.251188636)
        before = len(self.mock.requests)
        self.assertFalse(self.model.write("master", 1.0, confirm=lambda _: False))
        self.assertEqual(before, len(self.mock.requests))
        self.assertTrue(self.model.gain_adjust("master", 0.5, confirm=lambda _: True))
        self.assertLess(self.model.state["master"], 1.0)

    def test_refresh_rates_and_timeout_is_stale(self):
        self.model.start()
        self.model.refresh(now=0.0, force=True)
        self.model.refresh(now=0.1)
        self.assertEqual(1, len([x for x in self.mock.requests if x[0] == "/mixer/meters"]))
        self.model.refresh(now=0.15, force=True)
        self.assertEqual(1, len([x for x in self.mock.requests if x[0] == "/mixer/meters"]))
        self.model.refresh(now=METER_PERIOD + 0.01)
        self.assertEqual(2, len([x for x in self.mock.requests if x[0] == "/mixer/meters"]))
        self.model.refresh(now=5.1)
        self.assertEqual(1, self.model.health_time is not None)
        dead = ConsoleModel(OscClient(port=1, timeout=0.02), health_reader=lambda: {"ok": True})
        dead.state = {"master": 1.0}
        dead.refresh(now=0.0, force=True)
        self.assertIn("stale", dead.message)
        dead.client.close()

    def test_no_lifecycle_commands_and_stereo_y_is_inactive(self):
        source = Path(__file__).with_name("console.py").read_text()
        self.assertIn('subprocess.run(\n        ["amixer"', source)
        self.assertNotRegex(source, r"subprocess\.run\([^)]*(docker|jackd|systemctl|compose)")
        self.assertGreaterEqual(METER_PERIOD, 0.1)


if __name__ == "__main__":
    unittest.main()
