import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).parent))
from recorder_manager import RecorderManager
from recorder_policy import (EMERGENCY_RESERVE, RecorderState, bytes_per_second,
                             required_ready_bytes, required_start_bytes, segment_can_start, validate_target)
from mixerctl import read_config
from mixerctl import controls, group_controls, master_controls, node_update, validate_parameter
from contract import GROUPS
from source_map import validate_source_map


class RecorderPolicyTests(unittest.TestCase):
    def test_exact_multitrack_rate_and_two_hour_ready_gate(self):
        self.assertEqual(bytes_per_second(), 48_000 * 19 * 3)
        self.assertEqual(required_ready_bytes(), 2 * 3600 * 48_000 * 19 * 3)
        self.assertTrue(segment_can_start(EMERGENCY_RESERVE + bytes_per_second() * 900))
        self.assertFalse(segment_can_start(EMERGENCY_RESERVE + bytes_per_second() * 899))

    def test_start_capacity_includes_reserve_and_remaining_excludes_it(self):
        audio = required_ready_bytes(seconds=7200)
        reserve = EMERGENCY_RESERVE
        self.assertEqual(required_start_bytes(seconds=7200, reserve=reserve), audio + reserve)
        values, channels = read_config(Path(__file__).parents[1]/"payload/config/mixer.conf")
        manager = RecorderManager({"recording.emergency_reserve_bytes": str(reserve)}, values["_sources"], channels, launch=False)
        self.assertEqual(manager.remaining_seconds(audio + reserve), 7200)
        self.assertEqual(manager.remaining_seconds(reserve), 0)
        self.assertEqual(manager.remaining_seconds(reserve - 1), 0)
        self.assertEqual(manager.remaining_seconds(reserve + bytes_per_second() * 7), 7)
        print(f"recorder capacity: start boundary below={audio + reserve - 1}, "
              f"exact={audio + reserve}; remaining free below={reserve - 1}, "
              f"equal={reserve}, above={reserve + bytes_per_second() * 7}: OK")

    def test_mount_uuid_and_readonly_are_refused(self):
        self.assertEqual(validate_target("/tmp", "abc", "abc", True), "NO_RECORDING_DISK")
        self.assertEqual(validate_target("/recordings", "abc", "wrong", True), "NO_RECORDING_DISK")
        self.assertEqual(validate_target("/recordings", "abc", "abc", False), "NO_RECORDING_DISK")
        self.assertEqual(validate_target("/recordings", "abc", "abc", True,"xfs"), "NO_RECORDING_DISK")
        self.assertEqual(validate_target("/recordings", "abc", "abc", True), "READY")

    def test_segment_policy_and_emergency_stop(self):
        state=RecorderState("READY"); state.begin()
        self.assertFalse(state.next_segment(EMERGENCY_RESERVE))
        self.assertEqual(state.value,"FINAL_SEGMENT")
        state=RecorderState("RECORDING"); state.space_during_segment(EMERGENCY_RESERVE-1)
        self.assertEqual(state.value,"STOPPED_FULL")
        state.fail("removed",disk_lost=True); self.assertEqual(state.value,"DISK_LOST")

    def test_session_plan_tracks_mixed_stereo_sync_and_master(self):
        config=Path(__file__).parents[1]/"payload/config/mixer.conf"
        values,channels=read_config(config)
        entries=[source.snapshot() for source in values["_sources"]]
        entries[0]={"id":"rc202","name":"RC-202","mode":"stereo","inputs":[1,2],"group":"kick"}
        entries=[entry for entry in entries if entry["id"] not in ("drums_1","drums_2")]
        sources=validate_source_map(entries,tuple(values["group.names"].split(",")))
        with tempfile.TemporaryDirectory() as root:
            cfg={"recording.mount":root,"recording.uuid":"expected","recording.segment_seconds":"900"}
            manager=RecorderManager(cfg,sources,channels,launch=False,uuid_probe=lambda _:"expected")
            with mock.patch("recorder_manager.os.path.ismount",return_value=True), \
                 mock.patch("recorder_manager.shutil.disk_usage",return_value=SimpleNamespace(free=required_ready_bytes()+EMERGENCY_RESERVE)), \
                 mock.patch("recorder_manager.validate_target",return_value="READY"):
                first=manager.start(); second=manager.start()
            self.assertNotEqual(first,second)
            lines=(first/"tracks.tsv").read_text().splitlines()
            self.assertIn("rc202 2 0",lines)
            self.assertIn("sync 1 16",lines)
            self.assertIn("master 2 17",lines)
            metadata=(first/"session.json").read_text()
            self.assertIn('"physical_inputs": [\n        1,\n        2\n      ]',metadata)

    def test_authoritative_contract_exposes_group_dsp_recording_and_generator(self):
        values,channels=read_config(Path(__file__).parents[1]/"payload/config/mixer.conf")
        state=dict(controls(values,channels))
        self.assertEqual(len([key for key in state if key.startswith("groupLevel")]),8)
        for group in range(8):
            for suffix in ("Mute","EqBypass","EqLowDb","EqLowHz","EqLowMidDb","EqLowMidHz","EqHighMidDb","EqHighMidHz","EqHighDb","EqHighHz","CompBypass","CompThresholdDb","CompRatio","CompAttack","CompRelease","SatBypass","SatDrive","DuckAmountDb","DuckThreshold","DuckAttack","DuckRelease"):
                key=f"group{group}{suffix}"
                self.assertIn(key,state)
                self.assertEqual(node_update(key,1,values=values)[0],4000+group)
        for key in ("recordStart","recordStop","recorderState","recorderDiskFreeBytes","testGeneratorEnable","testGeneratorLevelDb","testGeneratorType","testGeneratorDestination"):
            self.assertIn(key,state)
        self.assertEqual(validate_parameter("testGeneratorLevelDb",-30,values),-30)
        with self.assertRaises(ValueError): validate_parameter("testGeneratorLevelDb",-20,values)
        self.assertEqual(GROUPS,tuple(values["group.names"].split(",")))

    def test_jack_capture_plan_uses_independent_inputs_and_final_master_ports(self):
        values, channels = read_config(Path(__file__).parents[1]/"payload/config/mixer.conf")
        manager = RecorderManager({"recording.master_prefix": "jack:out_"}, values["_sources"], channels, launch=False)
        calls = []

        def fake_run(args, **kwargs):
            calls.append(args[1:3])
            return SimpleNamespace(returncode=0, stderr="")

        with mock.patch("recorder_manager.subprocess.run", side_effect=fake_run):
            manager._connect_ports()
        self.assertEqual(len(calls), 19)
        self.assertEqual(calls[:2], [["system:capture_1", "sc-adat-recorder:capture_01"],
                                     ["system:capture_2", "sc-adat-recorder:capture_02"]])
        self.assertEqual(calls[-2:], [["jack:out_1", "sc-adat-recorder:capture_18"],
                                      ["jack:out_2", "sc-adat-recorder:capture_19"]])

    def test_quad_graph_keeps_its_existing_control_surface(self):
        values, channels = read_config(Path(__file__).parents[1]/"payload/config/mixer.conf")
        values["_mode"] = "quad"
        group_keys = {name for name, _ in group_controls(values, 0)}
        master_keys = {name for name, _ in master_controls(values)}
        self.assertTrue({"groupIndex", "gain", "x", "y", "width", "spatialBypass", "smoothing"}.issubset(group_keys))
        self.assertFalse(any(key.startswith(("eq", "comp", "sat", "duck")) for key in group_keys))
        self.assertEqual(master_keys, {"master", "smoothing"})

    def test_start_refuses_missing_disk_or_insufficient_capacity_without_launch(self):
        values, channels = read_config(Path(__file__).parents[1]/"payload/config/mixer.conf")
        config = {"recording.mount": "/recordings", "recording.uuid": "expected"}
        manager = RecorderManager(config, values["_sources"], channels,
                                  uuid_probe=lambda _path: "wrong")
        with mock.patch("recorder_manager.os.path.ismount", return_value=True), \
             mock.patch("recorder_manager.subprocess.check_output", return_value="ext4"), \
             mock.patch("recorder_manager.subprocess.Popen") as popen:
            with self.assertRaisesRegex(RuntimeError, "NO_RECORDING_DISK"):
                manager.start()
            popen.assert_not_called()
            self.assertIsNone(manager.session_dir)

        manager = RecorderManager(config, values["_sources"], channels, launch=False,
                                  uuid_probe=lambda _path: "expected")
        with mock.patch("recorder_manager.os.path.ismount", return_value=True), \
             mock.patch("recorder_manager.subprocess.check_output", return_value="ext4"), \
             mock.patch("recorder_manager.validate_target", return_value="READY"), \
             mock.patch("recorder_manager.shutil.disk_usage", return_value=SimpleNamespace(free=required_start_bytes()-1)):
            with self.assertRaisesRegex(RuntimeError, "space|capacity"):
                manager.start()
            self.assertIsNone(manager.session_dir)

        with tempfile.TemporaryDirectory() as root:
            manager = RecorderManager({"recording.mount": root, "recording.uuid": "expected",
                                      "recording.ready_seconds": "1",
                                      "recording.emergency_reserve_bytes": "100"}, values["_sources"], channels,
                                     launch=False, uuid_probe=lambda _path: "expected")
            manager._target = lambda: (root, "READY")
            with mock.patch("recorder_manager.shutil.disk_usage", return_value=SimpleNamespace(free=bytes_per_second()+100)):
                self.assertEqual(manager.start().parent, Path(root))
            below = RecorderManager({"recording.mount": root, "recording.uuid": "expected",
                                     "recording.ready_seconds": "1",
                                     "recording.emergency_reserve_bytes": "100"}, values["_sources"], channels,
                                    launch=False, uuid_probe=lambda _path: "expected")
            below._target = lambda: (root, "READY")
            with mock.patch("recorder_manager.shutil.disk_usage", return_value=SimpleNamespace(free=bytes_per_second()+99)):
                with self.assertRaisesRegex(RuntimeError, "space|capacity"):
                    below.start()

    def test_manager_construction_does_not_start_recording_automatically(self):
        values, channels = read_config(Path(__file__).parents[1]/"payload/config/mixer.conf")
        manager = RecorderManager({}, values["_sources"], channels)
        self.assertIsNone(manager.process)
        self.assertIsNone(manager.session_dir)

    def test_missing_recording_mount_never_reports_root_free_space(self):
        values, channels = read_config(Path(__file__).parents[1]/"payload/config/mixer.conf")
        manager = RecorderManager({}, values["_sources"], channels)
        manager._target = lambda: ("/recordings", "NO_RECORDING_DISK")
        with mock.patch("recorder_manager.shutil.disk_usage", return_value=SimpleNamespace(free=10**12)):
            state = manager.control_state()
        self.assertEqual(state["recorderState"], "NO_RECORDING_DISK")
        self.assertEqual(state["recorderDiskFreeBytes"], 0)
        self.assertEqual(state["recorderRemainingSeconds"], 0)

    def test_disk_loss_uses_priority_signal_and_preserves_unclean_metadata(self):
        values, channels = read_config(Path(__file__).parents[1]/"payload/config/mixer.conf")
        with tempfile.TemporaryDirectory() as root:
            manager = RecorderManager({"recording.mount": root}, values["_sources"], channels, launch=False)
            class RunningProcess:
                returncode = None
                signals = []
                def poll(self): return self.returncode
                def send_signal(self, signal): self.signals.append(signal)
            process = RunningProcess(); manager.process = process
            manager.session_dir = Path(root)/"session"; manager.session_dir.mkdir()
            (manager.session_dir/"session.json").write_text(json.dumps({"midi": {}, "clean_termination": True}))
            manager.last_mount_check = 0
            manager._target = lambda: (root, "NO_RECORDING_DISK")
            self.assertEqual(manager.status(), "DISK_LOST")
            import signal
            self.assertEqual(process.signals, [signal.SIGUSR1])
            self.assertEqual(manager.stop(), "DISK_LOST")
            self.assertEqual(process.signals, [signal.SIGUSR1, signal.SIGUSR1])
            process.returncode = 4
            (manager.session_dir/"recorder.status").write_text("state=DISK_LOST\ndropped_frames=0\nxrun_count=0\n")
            with mock.patch.object(manager, "_session_still_on_recording_mount", return_value=True):
                self.assertEqual(manager.status(), "DISK_LOST")
            metadata=json.loads((manager.session_dir/"session.json").read_text())
            self.assertFalse(metadata["clean_termination"])
            self.assertIn("UUID or writability", metadata["recorder_error"])
            self.assertNotIn(signal.SIGTERM, process.signals)
            print("recorder disk loss: UUID/mount loss -> DISK_LOST, "
                  "clean_termination=false, preserved UUID/writability error, "
                  "SIGUSR1 path retained and SIGTERM not substituted: OK")

    def test_invalid_or_colliding_session_configuration_creates_no_directory(self):
        values, channels = read_config(Path(__file__).parents[1]/"payload/config/mixer.conf")
        entries = [source.snapshot() for source in values["_sources"]]
        entries[0]["id"] = "same/name"
        entries[1]["id"] = "same_name"
        sources = validate_source_map(entries, GROUPS)
        with tempfile.TemporaryDirectory() as root:
            manager = RecorderManager({"recording.mount": root, "recording.uuid": "expected"},
                                      sources, channels, launch=False)
            manager._target = lambda: (root, "READY")
            with mock.patch("recorder_manager.shutil.disk_usage", return_value=SimpleNamespace(free=required_ready_bytes()+EMERGENCY_RESERVE)):
                with self.assertRaisesRegex(ValueError, "collide"):
                    manager.start()
            self.assertEqual(list(Path(root).iterdir()), [])

            invalid = RecorderManager({"recording.mount": root, "recording.uuid": "expected",
                                      "recording.segment_seconds": "not-an-integer"}, sources, channels)
            with self.assertRaisesRegex(ValueError, "segment_seconds"):
                invalid.start()


if __name__ == "__main__":
    unittest.main()
