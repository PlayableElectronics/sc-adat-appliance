#!/usr/bin/env python3
"""Mock-OSC tests for the development-only terminal console."""
import socket
import threading
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from console import (CHANNEL_FIELDS, GROUP_FIELDS, ConsoleModel, METER_PERIOD, MeterVisual,
                     OscClient, _confirm, _help, _handle_key, _layout_supported,
                     _next_page, db, meter_bar, parse_direct_entry, read_health,
                     resolve_rme_proc_path)
from mixerctl import METER_WIDTH, controls, packet, parse_packet, read_config, state_chunk_packets


class MockMixer:
    def __init__(self, complete=True):
        values, channels = read_config("../payload/config/mixer.conf")
        self.state = dict(controls(values, channels))
        self.requests = []
        self.reject = False
        self.complete = complete
        self.request_count = 0
        self.drop_chunks = set()
        self.drop_first_chunks = set()
        self.drop_done = False
        self.drop_first_done = False
        self.duplicate_chunk = None
        self.reorder = False
        self.mixed_snapshot = False
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(0.1)
        self.port = self.sock.getsockname()[1]
        self.stop = False
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def close(self):
        self.stop = True
        self.thread.join(timeout=1)
        self.sock.close()

    def run(self):
        while not self.stop:
            try:
                data, address = self.sock.recvfrom(65535)
            except (OSError, socket.timeout):
                continue
            path, _, values = parse_packet(data)
            self.requests.append((path, values))
            if path == "/mixer/get-all":
                self.request_count += 1
                chunks, done, legacy_done = state_chunk_packets(self.state, self.request_count)
                indexed = list(enumerate(chunks))
                if self.reorder:
                    indexed.reverse()
                drops = self.drop_chunks | (self.drop_first_chunks if self.request_count == 1 else set())
                for index, chunk in indexed:
                    if index in drops:
                        continue
                    if self.mixed_snapshot and index == 0:
                        path0, types0, values0 = parse_packet(chunk)
                        values0[0] = "stale-snapshot"
                        self.sock.sendto(packet(path0, types0, values0), address)
                    self.sock.sendto(chunk, address)
                    if index == self.duplicate_chunk:
                        self.sock.sendto(chunk, address)
                if self.complete and not self.drop_done and not (self.drop_first_done and self.request_count == 1):
                    if self.mixed_snapshot:
                        done_path, done_types, done_values = parse_packet(done)
                        done_values[0] = "stale-snapshot"
                        self.sock.sendto(packet(done_path, done_types, done_values), address)
                    self.sock.sendto(done, address)
                    self.sock.sendto(legacy_done, address)
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

    def test_polarity_requires_confirmation_and_cancel_sends_no_write(self):
        self.model.start()
        before = len(self.mock.requests)
        self.assertFalse(self.model.write("polarity0", -1, confirm=lambda _: False))
        self.assertEqual(before, len(self.mock.requests))
        self.assertTrue(self.model.write("polarity0", -1, confirm=lambda _: True))
        self.assertIn("/mixer/set", [path for path, _ in self.mock.requests])

    def test_incomplete_get_all_is_rejected(self):
        self.mock.complete = False
        with self.assertRaises(TimeoutError):
            self.model.start()
        self.assertNotIn("/mixer/set", [path for path, _ in self.mock.requests])

    def test_bulk_state_dropped_middle_chunk_recovers_on_bounded_retry(self):
        self.mock.drop_first_chunks = {1}
        self.model.start()
        self.assertEqual(self.mock.request_count, 2)
        self.assertEqual(self.model.state["controlContractVersion"], "1.0.0")

    def test_bulk_state_dropped_completion_fails_after_bounded_retries(self):
        self.mock.drop_done = True
        with self.assertRaises(TimeoutError):
            self.model.start()
        self.assertEqual(self.mock.request_count, 3)
        self.assertNotIn("/mixer/set", [path for path, _ in self.mock.requests])

    def test_bulk_state_duplicate_and_reordered_chunks(self):
        self.mock.duplicate_chunk = 2
        self.mock.reorder = True
        self.model.start()
        self.assertEqual(len(self.model.state), len(self.mock.state))

    def test_bulk_state_mixed_snapshot_fails_after_bounded_retries(self):
        self.mock.mixed_snapshot = True
        with self.assertRaises(TimeoutError):
            self.model.start()
        self.assertGreaterEqual(self.mock.request_count, 2)
        self.assertLessEqual(self.mock.request_count, 3)

    def test_bulk_state_datagrams_stay_below_contract_limit(self):
        chunks, done, legacy_done = state_chunk_packets(self.mock.state, "test")
        self.assertLessEqual(max(map(len, chunks + [done, legacy_done])), 1200)

    def test_contract_version_mismatch_refuses_operation(self):
        self.mock.state["controlContractVersion"] = "0.0.0"
        with self.assertRaises(RuntimeError):
            self.model.start()
        self.assertNotIn("/mixer/set", [path for path, _ in self.mock.requests])

    def test_missing_contract_version_refuses_operation(self):
        del self.mock.state["controlContractVersion"]
        with self.assertRaises(RuntimeError):
            self.model.start()
        self.assertNotIn("/mixer/set", [path for path, _ in self.mock.requests])

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


class FakeWindow:
    def __init__(self, keys):
        self.keys = list(keys)
        self.modes = []

    def nodelay(self, enabled):
        self.modes.append(enabled)

    def getmaxyx(self):
        return (24, 120)

    def addnstr(self, *_args):
        return None

    def refresh(self):
        return None

    def erase(self):
        return None

    def getch(self):
        return self.keys.pop(0) if self.keys else -1


class ConsoleModalTests(unittest.TestCase):
    def test_confirm_temporarily_blocks_and_non_y_cancels(self):
        accepted = FakeWindow([ord("Y")])
        self.assertTrue(_confirm(accepted, "confirm"))
        self.assertEqual([False, True], accepted.modes)
        cancelled = FakeWindow([ord("n")])
        self.assertFalse(_confirm(cancelled, "confirm"))
        self.assertEqual([False, True], cancelled.modes)

    def test_help_waits_for_real_key_and_restores_nonblocking(self):
        window = FakeWindow([-1, ord("x")])
        _help(window)
        self.assertEqual([False, True], window.modes)
        self.assertEqual([], window.keys)


class ConsoleUiTests(unittest.TestCase):
    def setUp(self):
        self.mock = MockMixer()
        self.model = ConsoleModel(OscClient(port=self.mock.port), health_reader=lambda: {"xruns": None})
        self.model.start()
        self.model.focus = "items"
        self.model.param = 0
        self.model.editing = None

    def tearDown(self):
        self.mock.close()
        self.model.client.close()

    def test_tab_changes_page_only_and_focus_moves_to_inspector(self):
        self.assertEqual(CHANNEL_FIELDS, ("trim", "mute", "polarity", "hpf", "hpfHz"))
        self.assertEqual(GROUP_FIELDS, ("level", "x", "width", "bypass"))
        _next_page(self.model)
        self.assertEqual(self.model.page, 2)
        self.assertEqual(self.model.focus, "items")
        self.assertEqual(self.model.param, 0)
        _handle_key(self.model, 261, FakeWindow([]))  # curses.KEY_RIGHT on Linux
        self.assertEqual(self.model.focus, "params")
        self.assertEqual(self.model.row, 0)
        self.assertNotIn("/mixer/set", [path for path, _ in self.mock.requests])

    def test_contract_derived_direct_entry_and_rejection(self):
        self.assertAlmostEqual(parse_direct_entry("-12 dB", "master"), 0.251188643, places=6)
        self.assertEqual(parse_direct_entry("500 Hz", "hpfHz0"), 500.0)
        with self.assertRaises(ValueError):
            self.model.write("hpfHz0", 20001)
        with self.assertRaises(ValueError):
            self.model.write("group0PosX", 2.0)

    def test_small_layout_fails_gracefully(self):
        self.assertFalse(_layout_supported(19, 100))
        self.assertFalse(_layout_supported(24, 83))
        self.assertTrue(_layout_supported(20, 84))

    def test_meter_scaling_smoothing_and_peak_hold(self):
        bar, state = meter_bar(0.0, 20)
        self.assertEqual(len(bar), 20); self.assertEqual(state, "silence")
        bar, state = meter_bar(0.8, 20)
        self.assertEqual(state, "near-clipping"); self.assertIn("=", bar)
        visual = MeterVisual(hold_seconds=1.0)
        visual.update(0.5, 0.2, 0.0)
        _, rms, hold = visual.update(0.0, 0.0, 0.1)
        self.assertGreater(rms, 0.0); self.assertGreater(hold, 0.4)
        _, _, decayed = visual.update(0.0, 0.0, 2.0)
        self.assertLess(decayed, hold)


class ConsoleHealthTests(unittest.TestCase):
    def _asound_tree(self, root):
        asound = root / "asound"
        card = asound / "card1"
        card.mkdir(parents=True)
        (asound / "cards").write_text(" 1 [Digi9652 ]: H9652 - RME Digi9652\n")
        (card / "id").write_text("Digi9652\n")
        (card / "rme9652").write_text("ADAT Sample rate: 48000Hz\n")
        return asound

    def test_rme_proc_path_is_dynamic(self):
        with tempfile.TemporaryDirectory() as directory:
            path = resolve_rme_proc_path(self._asound_tree(Path(directory)))
            self.assertEqual(path.name, "rme9652")
            self.assertEqual(path.parent.name, "card1")

    def test_missing_jack_log_reports_unknown_xruns(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            asound = self._asound_tree(root)
            with patch("console.read_alsa_control", return_value="AutoSync"):
                health = read_health(root / "missing-jack.log", asound, root / "proc")
            self.assertIsNone(health["xruns"])
            self.assertTrue(health["stale"])


if __name__ == "__main__":
    unittest.main()
