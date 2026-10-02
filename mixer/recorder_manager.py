"""Control-plane session and SSD policy for the independent JACK recorder."""
import json
import os
import re
import shutil
import subprocess
import stat
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from recorder_policy import bytes_per_second, required_ready_bytes, segment_can_start, validate_target
from contract import CONTRACT_VERSION


class RecorderManager:
    def __init__(self, config, sources, channels, launch=True, uuid_probe=None, executable=None, mixer_snapshot=None):
        self.config = dict(config)
        self.sources, self.channels = sources, channels
        self.mixer_snapshot=mixer_snapshot or {}
        self.launch = launch
        self.uuid_probe = uuid_probe or self._findmnt_uuid
        self.executable = executable or self.config.get("recorder.executable", "/usr/bin/sc-adat-recorder")
        self.process = None
        self.midi_process=None; self.midi_status="not configured"
        self.session_dir = None
        self.state = "NO_RECORDING_DISK"
        self.error = ""
        self.started_monotonic = None
        self.dropped_frames = 0
        self.xrun_count = 0
        self.last_mount_check = 0.0
        self.last_mount_ok = False

    def _integer_setting(self, name, default, minimum, maximum):
        try:
            value = int(self.config.get(name, default))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid recording setting {name}") from exc
        if not minimum <= value <= maximum:
            raise ValueError(f"recording setting {name} must be {minimum}..{maximum}")
        return value

    def _stop_midi(self):
        if self.midi_process is None:
            return
        import signal
        process = self.midi_process
        try:
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
            self.midi_status = "stopped" if process.returncode == 0 else f"stopped (exit {process.returncode})"
        except (OSError, subprocess.SubprocessError) as exc:
            self.midi_status = f"stop failed ({exc})"
        finally:
            self.midi_process = None

    def _connect_ports(self):
        capture_prefix=self.config.get("recording.capture_prefix","system:capture_")
        master_prefix=self.config.get("recording.master_prefix","jack:out_")
        targets=[(f"{capture_prefix}{index}",f"sc-adat-recorder:capture_{index:02d}") for index in range(1,18)]
        targets += [(f"{master_prefix}{index}",f"sc-adat-recorder:capture_{index+17:02d}") for index in (1,2)]
        for source,target in targets:
            result=subprocess.run([self.config.get("recording.jack_connect","/usr/bin/jack_connect"),source,target],
                                  stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,text=True,timeout=2)
            if result.returncode:
                raise RuntimeError(f"JACK capture connection failed: {source} -> {target}: {result.stderr.strip()}")

    @staticmethod
    def _findmnt_uuid(path):
        try:
            return subprocess.check_output(["findmnt", "-n", "-o", "UUID", "--target", path], text=True, timeout=2).strip()
        except (OSError, subprocess.SubprocessError):
            return ""

    def status(self):
        if self.midi_process is not None and self.midi_process.poll() is not None:
            self.midi_status="stopped" if self.state not in ("RECORDING","LOW_SPACE","FINAL_SEGMENT") else f"failed (exit {self.midi_process.returncode})"
            self.midi_process=None
        active_status=(self.session_dir/"recorder.status") if self.session_dir else None
        if active_status and active_status.is_file():
            try:
                fields=dict(line.split("=",1) for line in active_status.read_text().splitlines() if "=" in line)
                self.dropped_frames=int(fields.get("dropped_frames",self.dropped_frames)); self.xrun_count=int(fields.get("xrun_count","0"))
                if self.dropped_frames: self.error="JACK capture ring overflow; discontinuity recorded"
                if fields.get("state") in ("FINAL_SEGMENT","STOPPED_FULL","DISK_LOST","FAILED"): self.state=fields["state"]
            except (OSError,ValueError): self.error="unable to read recorder status"
        if self.process is not None and self.process.poll() is not None:
            status = self.session_dir / "recorder.status"
            if status.is_file():
                fields = dict(line.split("=", 1) for line in status.read_text().splitlines() if "=" in line)
                try:
                    self.state = fields.get("state", "FAILED")
                    self.dropped_frames=int(fields.get("dropped_frames", "0")); self.xrun_count=int(fields.get("xrun_count","0"))
                    self._stop_midi()
                    self.error = ("JACK capture ring overflow; audio discontinuity" if self.dropped_frames else
                                  "recorder I/O or capture failure" if self.state == "FAILED" else
                                  "recording disk became unavailable" if self.state == "DISK_LOST" else "")
                    metadata_path=self.session_dir / "session.json"; metadata=json.loads(metadata_path.read_text())
                    segments=sorted(item.name for item in self.session_dir.glob("segment-[0-9][0-9][0-9]"))
                    closed_cleanly=self.state in ("STOPPED", "STOPPED_FULL")
                    metadata["segment_list"]=[{"directory":name,"status":"finalized" if closed_cleanly or i < len(segments)-1 else "possibly_incomplete"}
                                               for i,name in enumerate(segments)]
                    metadata["state"]=self.state; metadata["clean_termination"]=closed_cleanly
                    metadata["recorder_error"]=self.error; metadata["xrun_count_stop"]=self.xrun_count
                    metadata["midi"]["status"]=self.midi_status
                    try: metadata["disk_free_bytes_stop"]=shutil.disk_usage(self.config.get("recording.mount","/recordings")).free
                    except OSError: metadata["disk_free_bytes_stop"]=None
                    metadata_path.write_text(json.dumps(metadata,indent=2)+"\n")
                except (OSError,ValueError,KeyError) as exc:
                    self.state="DISK_LOST"; self.error=f"finalization metadata failure: {exc}"
            elif self.state == "RECORDING":
                self.state, self.error = "FAILED", f"recorder exited {self.process.returncode}"
            self.process = None
        elif self.process is not None and self.process.poll() is None:
            now=time.monotonic()
            if now-self.last_mount_check>=5:
                root,state=self._target(); self.last_mount_ok=state=="READY"; self.last_mount_check=now
            if not self.last_mount_ok:
                self.state="DISK_LOST"; self.error="recording mount UUID or writability changed"
                self.process.terminate()
            else:
                root=self.config.get("recording.mount","/recordings")
                try:
                    if shutil.disk_usage(root).free < required_ready_bytes(seconds=int(self.config.get("recording.ready_seconds",7200))): self.state="LOW_SPACE"
                except OSError:
                    self.state="DISK_LOST"; self.error="recording mount disappeared"; self.process.terminate()
        elif self.process is None and self.state in ("NO_RECORDING_DISK","IDLE","READY","LOW_SPACE"):
            now=time.monotonic()
            if now-self.last_mount_check>=5:
                root,state=self._target(); self.last_mount_ok=state=="READY"; self.last_mount_check=now
            if self.last_mount_ok:
                root=self.config.get("recording.mount","/recordings")
                try: self.state="READY" if shutil.disk_usage(root).free>=required_ready_bytes(seconds=int(self.config.get("recording.ready_seconds",7200))) else "LOW_SPACE"
                except OSError: self.state="NO_RECORDING_DISK"
            else: self.state="NO_RECORDING_DISK"
        return self.state

    def control_state(self):
        current_state = self.status()
        root = self.config.get("recording.mount", "/recordings")
        free=0
        try:
            if self.last_mount_ok and os.path.ismount(root):
                if self.session_dir is None or os.stat(self.session_dir).st_dev == os.stat(root).st_dev:
                    free=shutil.disk_usage(root).free
        except OSError:
            free=0
        elapsed=max(0,int(time.monotonic()-self.started_monotonic)) if self.started_monotonic else 0
        segment=-1
        if self.session_dir:
            dirs=sorted(self.session_dir.glob("segment-[0-9][0-9][0-9]"))
            if dirs: segment=int(dirs[-1].name[-3:])
        return {"recorderState":current_state,"recorderElapsedSeconds":elapsed,"recorderSegment":segment,
                "recorderRemainingSeconds":self.remaining_seconds(free),"recorderDiskFreeBytes":free,
                "recorderDroppedFrames":self.dropped_frames,"recorderError":self.error}

    def _target(self):
        path = self.config.get("recording.mount", "/recordings")
        expected = self.config.get("recording.uuid", "")
        mounted = self.uuid_probe(path)
        try:
            fs_type=subprocess.check_output(["findmnt","-n","-o","FSTYPE","--target",path],text=True,timeout=2).strip()
        except (OSError,subprocess.SubprocessError): fs_type=""
        try:
            flags=os.statvfs(path).f_flag
            readonly=bool(flags & getattr(os, "ST_RDONLY", 1))
        except OSError:
            readonly=True
        writable = os.path.ismount(path) and os.access(path, os.W_OK) and not readonly
        return path, validate_target(path, expected, mounted, writable,fs_type)

    def start(self):
        segment_seconds = self._integer_setting("recording.segment_seconds", 900, 1, 7200)
        reserve = self._integer_setting("recording.emergency_reserve_bytes", 5368709120, 1, 2**63 - 1)
        ready_seconds = self._integer_setting("recording.ready_seconds", 7200, 1, 31536000)
        current_state = self.status()
        if self.process is not None or current_state in ("RECORDING", "FINAL_SEGMENT"):
            raise RuntimeError("recording already active")
        root, target_state = self._target()
        if target_state != "READY":
            self.state = "NO_RECORDING_DISK"
            raise RuntimeError(self.state)
        try: free = shutil.disk_usage(root).free
        except OSError:
            self.state="NO_RECORDING_DISK"; raise RuntimeError(self.state)
        if free < required_ready_bytes(seconds=ready_seconds):
            self.state = "LOW_SPACE"
            raise RuntimeError("less than two hours of recording capacity")
        session = Path(root) / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
        plan = []
        manifest = []
        used_names = set()
        for source in self.sources:
            safe = re.sub(r"[^A-Za-z0-9_.-]+", "_", source.id)
            if safe in used_names:
                raise ValueError("source IDs collide after recording filename normalization")
            used_names.add(safe)
            inputs = tuple(source.inputs)
            plan.append(f"{safe} {len(inputs)} {inputs[0]-1}")
            manifest.append({"file": safe + ".wav", "source_id": source.id, "name": source.name,
                             "group": source.group, "physical_inputs": list(inputs),
                             "mode": source.mode, "orientation": "L/R" if len(inputs) == 2 else "mono"})
        plan.extend(("sync 1 16", "master 2 17"))
        session.mkdir(mode=0o750, exist_ok=False)
        (session / "tracks.tsv").write_text("# filename channels first_zero_based_JACK_input\n" + "\n".join(plan) + "\n")
        metadata = {"session_id": session.name, "utc_start": datetime.now(timezone.utc).isoformat(),
                    "local_start": datetime.now().astimezone().isoformat(), "sample_rate": 48000,
                    "sample_format": "WAV PCM_24", "recording_uuid": self.config.get("recording.uuid"),"disk_free_bytes_start":free,
                    "sync": {"file": "sync.wav", "physical_input": 17},
                    "master": {"file": "master.wav", "tap": "scsynth stereo output after limiter"},
                    "sources": manifest, "segment_seconds": segment_seconds,
                    "segment_list": [], "state": "RECORDING", "midi": {"status": "not configured", "port": self.config.get("recording.midi_port", "")},
                    "xrun_count_start": 0, "xrun_count_stop": None,
                    "mixer_config": str(self.config.get("recording.mixer_config", "payload/config/mixer.conf")),
                    "mixer_config_snapshot": self.mixer_snapshot,
                    "control_contract_version": CONTRACT_VERSION, "git_build_identity": self.config.get("recording.build_identity",os.environ.get("SC_ADAT_BUILD_ID","unreported"))}
        (session / "session.json").write_text(json.dumps(metadata, indent=2) + "\n")
        self.session_dir = session
        if not self.launch:
            self.state = "READY"
            return session
        segment_arg = str(segment_seconds)
        reserve_arg = str(reserve)
        try:
            self.process = subprocess.Popen([self.executable, str(session), segment_arg, reserve_arg, str(session / "tracks.tsv")],
                                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                            close_fds=True)
            time.sleep(0.15)
            if self.process.poll() is not None:
                raise RuntimeError(f"recorder exited {self.process.returncode} during JACK startup")
            self._connect_ports()
        except Exception:
            if self.process is not None:
                self.process.terminate()
                try: self.process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.process.kill(); self.process.wait(timeout=3)
            self.process=None
            self.state="FAILED"
            try:
                metadata_path = session / "session.json"
                metadata = json.loads(metadata_path.read_text())
                metadata["state"] = "FAILED"
                metadata["clean_termination"] = False
                metadata["recorder_error"] = "recorder failed to initialize or JACK port connection failed"
                metadata["segment_list"] = []
                metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
            except (OSError, ValueError):
                pass
            raise
        self.state = "RECORDING"
        self.last_mount_ok=True; self.last_mount_check=time.monotonic()
        self.started_monotonic=time.monotonic()
        midi_port=self.config.get("recording.midi_port","").strip()
        if midi_port:
            try:
                self.midi_process=subprocess.Popen([self.config.get("recording.arecordmidi","/usr/bin/arecordmidi"),"--port",midi_port,str(session/"events.mid")],
                                                   stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,close_fds=True)
                time.sleep(0.1)
                if self.midi_process.poll() is not None:
                    self.midi_status=f"unavailable (exit {self.midi_process.returncode})"; self.midi_process=None
                else: self.midi_status="recording"
            except (OSError,subprocess.SubprocessError) as exc:
                self.midi_status=f"unavailable ({exc})"; self.midi_process=None
        return session

    def stop(self):
        self._stop_midi()
        if self.process is None:
            return self.status()
        self.process.terminate()
        self.state = "FINAL_SEGMENT"
        return self.state

    def remaining_seconds(self, free_bytes):
        return max(0, int(free_bytes / bytes_per_second()))
