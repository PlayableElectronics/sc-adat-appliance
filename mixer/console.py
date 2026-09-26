#!/usr/bin/env python3
"""Development-only curses OSC console for the SC-ADAT mixer.

This module is intentionally a replaceable client.  It owns no DSP state and
never starts, stops, probes, or reconfigures the audio runtime.
"""
import curses
import math
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

from contract import CONTRACT_VERSION, control_for_key, controls_for_scope
from mixerctl import GROUPS, METER_WIDTH, controls, dbamp, group_limits, packet, parse_packet, read_config, validate_parameter

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "payload/config/mixer.conf"
METER_PERIOD = 0.2
HEALTH_PERIOD = 5.0
OSC_TIMEOUT = 0.75
STATE_RETRIES = 3
GAIN_STEP_DB = 0.5
TRIM_MIN_DB = 20.0 * math.log10(0.0001)
TRIM_MAX_DB = 20.0 * math.log10(4.0)


def db(value):
    value = float(value)
    return "-inf" if value <= 0 else f"{20.0 * math.log10(value):+.1f}"


def clamp_db(value):
    return max(TRIM_MIN_DB, min(TRIM_MAX_DB, float(value)))


def meter_parts(values):
    if len(values) != METER_WIDTH or not all(math.isfinite(float(v)) for v in values):
        raise ValueError("meter packet is incomplete or non-finite")
    return {
        "input_peak": values[0:16], "input_rms": values[16:32],
        "group_peak": values[32:40], "group_rms": values[40:48],
        "output_peak": values[48:64], "output_rms": values[64:80],
    }


class OscClient:
    """One-shot UDP OSC requests; no retries or lifecycle operations."""

    def __init__(self, host="127.0.0.1", port=57120, timeout=OSC_TIMEOUT, sock=None):
        self.address = (host, int(port))
        self.sock = sock or socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(timeout)

    def _request(self, data, expected=None):
        self.sock.sendto(data, self.address)
        deadline = time.monotonic() + OSC_TIMEOUT
        while time.monotonic() < deadline:
            message = parse_packet(self.sock.recv(65535))
            if expected is None or message[0] in expected:
                return message
        raise TimeoutError("OSC response timed out")

    def close(self):
        self.sock.close()

    def get_all(self):
        last_error = "OSC bulk state incomplete"
        for attempt in range(STATE_RETRIES):
            self.sock.sendto(packet("/mixer/get-all", ","), self.address)
            chunks = {}
            snapshot = None
            completion = None
            deadline = time.monotonic() + OSC_TIMEOUT
            try:
                while time.monotonic() < deadline:
                    path, types, values = parse_packet(self.sock.recv(65535))
                    if path == "/mixer/state-chunk":
                        if len(values) < 3 or types[:4] != ",sii":
                            raise ValueError("malformed mixer state chunk")
                        chunk_snapshot, index, total = str(values[0]), int(values[1]), int(values[2])
                        if snapshot is None:
                            snapshot = chunk_snapshot
                        if chunk_snapshot != snapshot:
                            raise ValueError("mixed mixer state snapshots")
                        if total <= 0 or index < 0 or index >= total:
                            raise ValueError("invalid mixer state chunk index")
                        pairs = values[3:]
                        pair_types = types[4:]
                        if len(pairs) != len(pair_types) or len(pairs) % 2:
                            raise ValueError("malformed mixer state chunk pairs")
                        entries = {}
                        for offset in range(0, len(pairs), 2):
                            if pair_types[offset] != "s" or pair_types[offset + 1] not in "fs":
                                raise ValueError("invalid mixer state chunk value type")
                            entries[str(pairs[offset])] = pairs[offset + 1]
                        if index in chunks and chunks[index] != (total, entries):
                            raise ValueError("conflicting duplicate mixer state chunk")
                        chunks[index] = (total, entries)
                    elif path == "/mixer/state-complete":
                        if len(values) != 3 or types != ",sii":
                            raise ValueError("legacy or malformed mixer completion record")
                        done_snapshot, chunk_count, entry_count = str(values[0]), int(values[1]), int(values[2])
                        if snapshot is None:
                            snapshot = done_snapshot
                        if done_snapshot != snapshot:
                            raise ValueError("mixed mixer completion snapshot")
                        completion = (chunk_count, entry_count)
                    if completion is not None:
                        chunk_count, entry_count = completion
                        if (len(chunks) == chunk_count and set(chunks) == set(range(chunk_count))):
                            state = {}
                            for index in range(chunk_count):
                                announced, entries = chunks[index]
                                if announced != chunk_count:
                                    raise ValueError("inconsistent mixer chunk count")
                                state.update(entries)
                            if len(state) != entry_count:
                                raise ValueError("mixer state entry count mismatch")
                            return state
                last_error = "OSC bulk state missing chunks or completion"
            except (socket.timeout, ValueError, IndexError, TypeError) as exc:
                last_error = str(exc)
        raise TimeoutError(f"OSC get-all failed after {STATE_RETRIES} attempts: {last_error}")

    def get(self, key):
        path, _, values = self._request(packet("/mixer/get", ",s", [key]), {"/mixer/state", "/mixer/error"})
        if path == "/mixer/error":
            raise RuntimeError(str(values[0] if values else "mixer error"))
        return values[1]

    def meters(self):
        path, _, values = self._request(packet("/mixer/meters", ","), {"/mixer/meters"})
        if path != "/mixer/meters":
            raise RuntimeError("unexpected meter response")
        return meter_parts([float(v) for v in values])

    def set_and_readback(self, key, value):
        path, _, values = self._request(packet("/mixer/set", ",sf", [key, value]), {"/mixer/ok", "/mixer/error"})
        if path == "/mixer/error":
            raise RuntimeError(str(values[0] if values else "mixer rejected control"))
        if not values or values[0] != key:
            raise RuntimeError("mixer acknowledgement did not identify the key")
        return self.get(key)


def read_alsa_control(name):
    result = subprocess.run(
        ["amixer", "-c", "Digi9652", "cget", f"name={name}"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        check=True,
    ).stdout
    items = {int(n): value for n, value in re.findall(r"Item #(\d+) '([^']+)'", result)}
    match = re.search(r"^\s*: values=([-+]?\d+)", result, re.MULTILINE)
    if not match:
        raise ValueError(f"ALSA control {name} has no value")
    return items.get(int(match.group(1)), "unknown")


def resolve_rme_proc_path(asound_root=Path("/proc/asound")):
    """Resolve the RME proc file without assuming it is ALSA card zero."""
    card_numbers = []
    try:
        for line in (asound_root / "cards").read_text(encoding="utf-8").splitlines():
            match = re.match(r"^\s*(\d+)\s+\[([^]]+)\]", line)
            if match and match.group(2).strip() == "Digi9652":
                card_numbers.append(match.group(1))
    except OSError:
        pass
    for card_dir in sorted(asound_root.glob("card*/")):
        try:
            if (card_dir / "id").read_text(encoding="utf-8").strip() == "Digi9652":
                number = card_dir.name.removeprefix("card")
                if number not in card_numbers:
                    card_numbers.append(number)
        except OSError:
            continue
    for number in card_numbers:
        path = asound_root / f"card{number}" / "rme9652"
        if path.is_file():
            return path
    return None


def read_health(log_path=None, asound_root=Path("/proc/asound"), proc_root=Path("/proc")):
    """Read hardware/process state without creating a JACK client."""
    health = {"stale": False, "clock": {}, "jack": {}, "xruns": None}
    try:
        health["clock"] = {
            "mode": read_alsa_control("Sync Mode"),
            "source": read_alsa_control("Preferred Sync Source"),
            "adat1": read_alsa_control("ADAT1 Sync Check"),
            "adat2": read_alsa_control("ADAT2 Sync Check"),
            "adat3": read_alsa_control("ADAT3 Sync Check"),
        }
    except (OSError, subprocess.CalledProcessError, ValueError) as exc:
        health["error"] = str(exc)
    try:
        proc_path = resolve_rme_proc_path(asound_root)
        if proc_path is None:
            raise FileNotFoundError("Digi9652 RME proc state unavailable")
        proc = proc_path.read_text(encoding="utf-8")
        match = re.search(r"^ADAT Sample rate:\s*(\d+)Hz", proc, re.MULTILINE)
        health["clock"]["rate"] = int(match.group(1)) if match else None
    except OSError as exc:
        health["clock"]["rate"] = None
        health["stale"] = True
        health["error"] = str(exc)
    try:
        proc_entries = proc_root.iterdir()
        for entry in proc_entries:
            if not entry.name.isdigit():
                continue
            try:
                if (entry / "comm").read_text().strip() != "jackd":
                    continue
                args = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
                health["jack"] = {
                    "rate": _arg_int(args, r"-r(\d+)"),
                    "period": _arg_int(args, r"-p(\d+)"),
                    "periods": _arg_int(args, r"-n(\d+)"),
                    "device": _arg_text(args, r"-d(\S+)"),
                    "rt": _jack_rt_priority(entry),
                }
                break
            except (OSError, ValueError):
                continue
    except OSError as exc:
        health["stale"] = True
        health.setdefault("error", str(exc))
    log = Path(log_path) if log_path else ROOT / ".local/sc-audio-logs/jack.log"
    try:
        text = log.read_text(encoding="utf-8", errors="replace")
        health["xruns"] = len(re.findall(r"xrun|process error|underrun|overrun", text, re.I))
    except OSError:
        health["xruns"] = None
        health["stale"] = True
    return health


def _arg_int(text, pattern):
    match = re.search(pattern, text)
    return int(match.group(1)) if match else None


def _arg_text(text, pattern):
    match = re.search(pattern, text)
    return match.group(1) if match else None


def _jack_rt_priority(proc):
    for task in (proc / "task").iterdir():
        try:
            policy = os.sched_getscheduler(int(task.name))
            if policy == getattr(os, "SCHED_FIFO", 1):
                return os.sched_getparam(int(task.name)).sched_priority
        except (OSError, ValueError):
            pass
    return None


class ConsoleModel:
    """State, validation, and interaction policy independent of curses."""

    def __init__(self, client, config_path=CONFIG, health_reader=read_health):
        self.client = client
        self.values, self.channels = read_config(str(config_path))
        self.groups = list(GROUPS)
        self.health_reader = health_reader
        self.state = {}
        self.initial = {}
        self.meters = None
        self.meter_time = None
        self.health = {}
        self.health_time = None
        self.page = 1
        self.row = 0
        self.field = 0
        self.message = ""
        self.changed = {}
        self.last_meter_request = -METER_PERIOD
        self.last_health_request = -HEALTH_PERIOD

    def start(self):
        self.state = self.client.get_all()
        if self.state.get("controlContractVersion") != CONTRACT_VERSION:
            raise RuntimeError("mixer control contract mismatch: " + str(self.state.get("controlContractVersion", "unavailable")))
        required = {key for key, _ in controls(self.values, self.channels)}
        missing = sorted(required - set(self.state))
        if missing:
            raise RuntimeError("OSC get-all incomplete; missing: " + ", ".join(missing))
        self.initial = dict(self.state)
        self.message = "Connected; no controls changed"

    def refresh(self, now=None, force=False):
        now = time.monotonic() if now is None else now
        # `force` refreshes the complete OSC state, but cannot bypass the
        # meter rate limit.  This keeps repeated `r` presses below 10 Hz.
        if now - self.last_meter_request >= METER_PERIOD:
            try:
                self.meters = self.client.meters()
                self.meter_time = now
                self.last_meter_request = now
            except (OSError, TimeoutError, ValueError, RuntimeError) as exc:
                self.message = f"meters stale: {exc}"
                self.last_meter_request = now
        if now - self.last_health_request >= HEALTH_PERIOD:
            try:
                self.health = self.health_reader()
                self.health_time = now
            except Exception as exc:  # health is advisory and must not affect audio
                self.health = {"error": str(exc)}
            self.last_health_request = now

    def stale(self, now=None):
        return self.meter_time is None or (time.monotonic() if now is None else now) - self.meter_time > 1.0

    def validate(self, key, value):
        if key.endswith("PosY"):
            raise ValueError("Y is quad only / inactive in stereo")
        if key.startswith("trim"):
            return validate_parameter(key, _amp_from_db(float(value)), self.values)
        return validate_parameter(key, value, self.values)

    def write(self, key, value, confirm=None):
        value = self.validate(key, value)
        old = self.state.get(key)
        definition, _ = control_for_key(key)
        prompt = None
        confirmation = definition.get("confirmation") if definition else None
        if confirmation == "increase" and old is not None and value > float(old):
            prompt = f"Increase master {db(old)} dB -> {db(value)} dB? y/N"
        elif confirmation == "always":
            prompt = f"Apply polarity inversion to {key}? y/N"
        if prompt is not None:
            if confirm is None or not confirm(prompt):
                self.message = "control change cancelled"
                return False
        try:
            readback = self.client.set_and_readback(key, value)
        except (OSError, TimeoutError, RuntimeError, ValueError) as exc:
            self.message = f"write failed; audio untouched: {exc}"
            return False
        self.state[key] = readback
        if self.initial.get(key) != readback:
            self.changed[key] = readback
        else:
            self.changed.pop(key, None)
        self.message = f"{key} acknowledged/read back: {readback}"
        return True

    def gain_adjust(self, key, delta_db, confirm=None):
        current = float(self.state.get(key, 1.0))
        current_db = -80.0 if current <= 0.0001 else 20.0 * math.log10(current)
        value = clamp_db(current_db + delta_db) if key.startswith("trim") else dbamp(current_db + delta_db)
        return self.write(key, value, confirm)

    def adjust_parameter(self, key, direction, coarse=False, confirm=None):
        definition, _ = control_for_key(key)
        if not definition:
            raise ValueError(f"{key} is not in the control contract")
        if definition["value_type"] == "boolean":
            return self.bool_toggle(key)
        if definition.get("enumerated_steps"):
            steps = definition["enumerated_steps"]
            current = float(self.state.get(key, steps[0]))
            index = min(range(len(steps)), key=lambda i: abs(steps[i] - current))
            return self.write(key, steps[max(0, min(len(steps) - 1, index + direction))], confirm)
        increments = definition.get("increments") or {}
        step = increments.get("coarse" if coarse else "fine")
        if definition["unit"] == "dB":
            return self.gain_adjust(key, direction * step, confirm)
        current = float(self.state.get(key, 0.5))
        return self.write(key, current + direction * step, confirm)

    def bool_toggle(self, key, confirm=None):
        return self.write(key, 0 if int(float(self.state.get(key, 0))) else 1, confirm)

    def summary(self):
        return dict(self.changed)


CHANNEL_DEFS = tuple(item for item in controls_for_scope("channel") if item["key_template"] != "channelNGroup")
HPF_STEPS = tuple(next(item for item in CHANNEL_DEFS if item["key_template"] == "hpfHzN")["enumerated_steps"])
CHANNEL_FIELDS = tuple(item["key_template"].removesuffix("N") for item in CHANNEL_DEFS)
GROUP_DEFS = controls_for_scope("group", "stereo")


def _group_field_name(template):
    return template.replace("groupLevelN", "level").replace("groupN", "").replace("Pos", "").replace("SpatialBypass", "bypass").lower()


GROUP_FIELDS = tuple(_group_field_name(item["key_template"]) for item in GROUP_DEFS)
PAGE_NAMES = {1: "CHANNELS", 2: "GROUPS", 3: "MASTER / STATUS"}
MIN_LAYOUT = (20, 84)


def channel_key(row, field):
    definition = next(item for item in CHANNEL_DEFS if item["key_template"].removesuffix("N") == field)
    return definition["key_template"].replace("N", str(row))


def group_key(row, field):
    definition = next(item for item in GROUP_DEFS if _group_field_name(item["key_template"]) == field)
    return definition["key_template"].replace("N", str(row))


def _field_definition(scope, field):
    definitions = CHANNEL_DEFS if scope == "channel" else GROUP_DEFS
    if scope == "channel":
        return next(item for item in definitions if item["key_template"].removesuffix("N") == field)
    return next(item for item in definitions if _group_field_name(item["key_template"]) == field)


def _db_value(value):
    return f"{db(value)} dB"


def _display_control_value(model, key, definition):
    value = model.state.get(key, 0)
    if definition["unit"] == "dB": return _db_value(value)
    if definition["value_type"] == "boolean": return "ON" if int(float(value)) else "OFF"
    if definition["value_type"] == "enum" and key.startswith("polarity"): return "INVERTED" if float(value) < 0 else "NORMAL"
    if definition["unit"] == "Hz": return f"{float(value):.0f} Hz"
    return f"{float(value):.2f}"


def _amp_from_db(text):
    return dbamp(float(text))


def parse_direct_entry(text, key):
    """Parse operator-facing units; validation remains in ConsoleModel.write."""
    value = text.strip()
    if not value:
        raise ValueError("empty numeric entry")
    definition, _ = control_for_key(key)
    if not definition:
        raise ValueError(f"{key} is not in the control contract")
    if key.startswith("trim"):
        return float(value.removesuffix("dB").strip())
    if definition["unit"] == "dB":
        return _amp_from_db(value.removesuffix("dB").strip())
    return float(value.removesuffix("Hz").strip())


def _dbfs(value):
    value = float(value)
    return -60.0 if value <= 0 else max(-60.0, min(0.0, 20.0 * math.log10(value)))


def meter_bar(value, width=20, peak_hold=None):
    """Return a theme-independent bar and state for an amplitude meter."""
    level = _dbfs(value)
    filled = int(round((level + 60.0) / 60.0 * max(1, width)))
    filled = max(0, min(width, filled))
    bar = "=" * filled + "." * (width - filled)
    if peak_hold is not None:
        marker = int(round((_dbfs(peak_hold) + 60.0) / 60.0 * max(1, width)))
        if 0 < marker <= width:
            bar = bar[:marker - 1] + "|" + bar[marker:]
    state = "silence" if level <= -59.5 else "near-clipping" if level >= -3 else "hot" if level >= -12 else "signal"
    return bar, state


class MeterVisual:
    """UI-only RMS smoothing and peak hold; it never changes OSC meter data."""
    def __init__(self, hold_seconds=1.0, decay_db_per_second=18.0):
        self.rms = 0.0
        self.peak_hold = 0.0
        self.last_time = None
        self.hold_until = 0.0
        self.hold_seconds = hold_seconds
        self.decay_db_per_second = decay_db_per_second

    def update(self, peak, rms, now):
        peak = max(0.0, float(peak)); rms = max(0.0, float(rms))
        dt = 0.0 if self.last_time is None else max(0.0, now - self.last_time)
        alpha = 1.0 - math.exp(-dt / 0.12) if dt else 1.0
        self.rms += (rms - self.rms) * alpha
        if peak >= self.peak_hold:
            self.peak_hold = peak
            self.hold_until = now + self.hold_seconds
        elif now > self.hold_until and dt:
            self.peak_hold = max(0.0, self.peak_hold * dbamp(-self.decay_db_per_second * dt))
        self.last_time = now
        return peak, self.rms, self.peak_hold


def _selection_text(text, width, selected):
    marker = "[SELECTED] " if selected else "           "
    return (marker + text)[:width].ljust(width)


def _layout_supported(h, w):
    return h >= MIN_LAYOUT[0] and w >= MIN_LAYOUT[1]


def _next_page(model):
    model.page = model.page % 3 + 1
    model.row = 0
    model.param = 0
    model.focus = "items"
    model.editing = None


def _meter_line(label, peak, rms, visual, width=24, now=None):
    now = time.monotonic() if now is None else now
    _, smooth_rms, held = visual.update(peak, rms, now)
    bar, state = meter_bar(smooth_rms, width, held)
    return f"{label:<5} [{bar}] {state:<13} peak {db(peak):>6} RMS {db(smooth_rms):>6} hold {db(held):>6}"


def _visual(model, key):
    visuals = getattr(model, "meter_visuals", None)
    if visuals is None:
        model.meter_visuals = {}
        visuals = model.meter_visuals
    return visuals.setdefault(key, MeterVisual())


def draw(stdscr, model):
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.keypad(True)
    model.focus = getattr(model, "focus", "items")
    model.param = getattr(model, "param", 0)
    model.coarse = getattr(model, "coarse", False)
    model.editing = None
    while True:
        now = time.monotonic()
        model.refresh(now)
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        if _layout_supported(h, w):
            _line(stdscr, 0, f"SC-ADAT development console  [{PAGE_NAMES[model.page]}]  focus={model.focus}  ({'coarse' if model.coarse else 'fine'})", curses.A_BOLD)
            if model.page == 1: _draw_channels(stdscr, model, now)
            elif model.page == 2: _draw_groups(stdscr, model, now)
            else: _draw_status(stdscr, model, now)
            footer = "Tab page  Up/Down select  Left/Right focus/adjust  Enter edit  Esc list  c coarse  m/h/p/b toggles  ? help  q quit"
        else:
            _draw_small(stdscr, h, w)
            footer = "Terminal too small; resize to at least 84x20. q quit  ? help"
        if model.message: footer = f"{model.message} | {footer}"
        _line(stdscr, h - 1, footer[-max(1, w - 1):])
        stdscr.refresh()
        key = stdscr.getch()
        if key == -1:
            time.sleep(0.03); continue
        if key in (ord("q"), ord("Q")): return
        if key == ord("?"): _help(stdscr); continue
        if key == 9:
            _next_page(model); continue
        if key in (ord("1"), ord("2"), ord("3")):
            model.page = int(chr(key)); model.row = 0; model.param = 0; model.focus = "items"; model.editing = None; continue
        if not _layout_supported(h, w): continue
        try:
            if model.editing is not None:
                _handle_edit(model, key, stdscr)
            else:
                _handle_key(model, key, stdscr)
        except ValueError as exc:
            model.message = str(exc)


def _draw_small(stdscr, h, w):
    _line(stdscr, max(1, h // 2 - 1), "Console layout unavailable")
    _line(stdscr, max(1, h // 2), "Resize terminal to at least 84 columns x 20 rows.")


def _selected_key(model):
    if model.page == 1:
        return channel_key(model.row, CHANNEL_FIELDS[model.param])
    if model.page == 2:
        return group_key(model.row, GROUP_FIELDS[model.param])
    return "master"


def _begin_edit(model):
    key = _selected_key(model)
    definition, _ = control_for_key(key)
    if not definition or definition["value_type"] in ("boolean", "enum"):
        model.message = "select a numeric control for direct editing"
        return
    value = model.state.get(key, 0.0)
    text = db(value) if definition["unit"] == "dB" else str(value)
    model.editing = (key, definition["label"], text)


def _handle_edit(model, key, stdscr):
    if key == 27:
        model.editing = None
        model.message = "numeric edit cancelled"
        return
    edit_key, label, text = model.editing
    if key in (curses.KEY_BACKSPACE, 127, 8):
        model.editing = (edit_key, label, text[:-1])
        return
    if key in (10, 13):
        try:
            value = parse_direct_entry(text, edit_key)
            model.write(edit_key, value, lambda prompt: _confirm(stdscr, prompt))
            model.editing = None
        except ValueError as exc:
            model.message = f"entry rejected: {exc}"
        return
    if 32 <= key <= 126 and chr(key) in "0123456789.-":
        model.editing = (edit_key, label, text + chr(key))


def _handle_key(model, key, stdscr):
    confirm = lambda prompt: _confirm(stdscr, prompt)
    count = 16 if model.page == 1 else 8 if model.page == 2 else 1
    if key == 27:
        model.focus = "items"
        return
    if key == ord("c"):
        model.coarse = not model.coarse
        model.message = "coarse 3 dB / 0.20 steps" if model.coarse else "fine steps"
        return
    if key == ord("r"):
        try:
            fresh = model.client.get_all()
            if fresh.get("controlContractVersion") != CONTRACT_VERSION:
                raise RuntimeError("mixer control contract mismatch")
            model.state.update(fresh); model.message = "complete state refreshed"
        except Exception as exc:
            model.message = f"refresh failed; audio untouched: {exc}"
        return
    if key in (curses.KEY_UP, curses.KEY_DOWN):
        if model.focus == "items":
            model.row = max(0, min(count - 1, model.row + (1 if key == curses.KEY_DOWN else -1)))
        else:
            fields = CHANNEL_FIELDS if model.page == 1 else GROUP_FIELDS if model.page == 2 else ("master",)
            model.param = max(0, min(len(fields) - 1, model.param + (1 if key == curses.KEY_DOWN else -1)))
        return
    if key == curses.KEY_LEFT:
        if model.focus == "items": model.focus = "params"
        else: model.adjust_parameter(_selected_key(model), -1, model.coarse, confirm)
        return
    if key == curses.KEY_RIGHT:
        if model.focus == "items": model.focus = "params"
        else: model.adjust_parameter(_selected_key(model), 1, model.coarse, confirm)
        return
    if key in (10, 13) and model.focus == "params":
        _begin_edit(model)
        return
    if key == ord("m") and model.page == 1:
        model.bool_toggle(channel_key(model.row, "mute")); return
    if key == ord("h") and model.page == 1:
        model.bool_toggle(channel_key(model.row, "hpf")); return
    if key == ord("p") and model.page == 1:
        polarity = channel_key(model.row, "polarity")
        model.write(polarity, -1 if float(model.state.get(polarity, 1)) == 1 else 1, confirm); return
    if key == ord("b") and model.page == 2:
        model.bool_toggle(group_key(model.row, "bypass")); return


def _panel_row(stdscr, y, x, width, text, selected=False):
    _line_at(stdscr, y, x, _selection_text(text, width, selected), curses.A_REVERSE if selected else 0)


def _draw_channels(stdscr, model, now):
    h, w = stdscr.getmaxyx(); left, centre = 25, 34; right = w - left - centre - 2
    _line_at(stdscr, 1, 0, "CHANNELS")
    _line_at(stdscr, 1, left + 1, "SELECTED CHANNEL")
    _line_at(stdscr, 1, left + centre + 2, "SIGNAL")
    for i, row in enumerate(model.channels):
        text = f"{i + 1:02d} {row['name'][:12]:12s} {row['group'][:8]:8s}"
        _panel_row(stdscr, i + 2, 0, left, text, i == model.row and model.focus == "items")
    row = model.channels[model.row]
    _line_at(stdscr, 2, left + 1, f"Channel {model.row + 1}: {row['name']}  group={row['group']}")
    fields = [(field, _field_definition("channel", field)["label"], _display_control_value(model, channel_key(model.row, field), _field_definition("channel", field))) for field in CHANNEL_FIELDS]
    for i, (_, label, value) in enumerate(fields):
        _panel_row(stdscr, i + 4, left + 1, centre, f"{label:<14} {value}", i == model.param and model.focus == "params")
    if model.editing: _line_at(stdscr, 10, left + 1, f"EDIT {model.editing[1]}: {model.editing[2]}_")
    values = model.meters or {"input_peak": [0] * 16, "input_rms": [0] * 16}
    _line_at(stdscr, 2, left + centre + 2, "-60 dBFS".ljust(max(1, right)))
    _line_at(stdscr, 3, left + centre + 2, _meter_line("IN", values["input_peak"][model.row], values["input_rms"][model.row], _visual(model, f"input{model.row}"), max(10, right - 5), now))
    _line_at(stdscr, 5, left + centre + 2, "Exact diagnostic values")
    _line_at(stdscr, 6, left + centre + 2, f"peak {db(values['input_peak'][model.row])} dBFS")
    _line_at(stdscr, 7, left + centre + 2, f"RMS  {db(values['input_rms'][model.row])} dBFS")


def _draw_groups(stdscr, model, now):
    h, w = stdscr.getmaxyx(); left, centre = 21, 38; right = w - left - centre - 2
    _line_at(stdscr, 1, 0, "GROUPS")
    _line_at(stdscr, 1, left + 1, "SELECTED GROUP")
    _line_at(stdscr, 1, left + centre + 2, "SIGNAL / MEMBERS")
    for i, name in enumerate(GROUPS): _panel_row(stdscr, i + 2, 0, left, f"{i + 1} {name}", i == model.row and model.focus == "items")
    name = GROUPS[model.row]
    limits = group_limits(model.values, name)
    fields = [(field, _field_definition("group", field)["label"], _display_control_value(model, group_key(model.row, field), _field_definition("group", field))) for field in GROUP_FIELDS]
    for i, (_, label, value) in enumerate(fields): _panel_row(stdscr, i + 3, left + 1, centre, f"{label:<18} {value}", i == model.param and model.focus == "params")
    _line_at(stdscr, 8, left + 1, "Y: QUAD ONLY (inactive in stereo)")
    _line_at(stdscr, 9, left + 1, f"Allowed X {limits[0]:.2f}..{limits[1]:.2f}  width {limits[4]:.2f}..{limits[5]:.2f}")
    vals = model.meters or {"group_peak": [0] * 8, "group_rms": [0] * 8}
    _line_at(stdscr, 3, left + centre + 2, _meter_line("GROUP", vals["group_peak"][model.row], vals["group_rms"][model.row], _visual(model, f"group{model.row}"), max(10, right - 5), now))
    _line_at(stdscr, 5, left + centre + 2, "Members")
    members = [f"{i + 1:02d} {ch['name']}" for i, ch in enumerate(model.channels) if ch["group"] == name]
    for i, member in enumerate(members[:max(1, h - 8)]): _line_at(stdscr, 6 + i, left + centre + 2, member)


def _draw_status(stdscr, model, now):
    h, w = stdscr.getmaxyx(); vals = model.meters or {"output_peak": [0] * 16, "output_rms": [0] * 16}
    _line_at(stdscr, 1, 0, "MASTER / STATUS")
    _line_at(stdscr, 3, 0, _meter_line("LEFT", vals["output_peak"][0], vals["output_rms"][0], _visual(model, "outputL"), max(20, w - 12), now))
    _line_at(stdscr, 5, 0, _meter_line("RIGHT", vals["output_peak"][1], vals["output_rms"][1], _visual(model, "outputR"), max(20, w - 12), now))
    master = model.state.get("master", 0.0)
    _panel_row(stdscr, 8, 0, min(w - 1, 45), f"Master {_db_value(master)} amplitude={float(master):.9f}", model.focus == "params")
    _line_at(stdscr, 10, 0, "Master: Left/Right fine 0.5 dB; c coarse 3 dB; Enter direct edit; increases confirm")
    clock = model.health.get("clock", {}); jack = model.health.get("jack", {})
    rate = "unavailable" if clock.get("rate") is None else clock.get("rate")
    xruns = "unknown" if model.health.get("xruns") is None else model.health.get("xruns")
    age = "stale" if model.stale(now) else f"{now - model.meter_time:.1f}s old"
    _line_at(stdscr, 12, 0, f"Meters: {age}")
    _line_at(stdscr, 13, 0, f"RME: mode={clock.get('mode','?')} source={clock.get('source','?')} ADAT1={clock.get('adat1','?')} ADAT2={clock.get('adat2','?')} ADAT3={clock.get('adat3','?')} rate={rate}")
    _line_at(stdscr, 14, 0, f"JACK: device={jack.get('device','?')} rate={jack.get('rate','?')} period={jack.get('period','?')} periods={jack.get('periods','?')} RT={jack.get('rt','?')} xruns={xruns}")


def _line_at(stdscr, y, x, text, attr=0):
    try:
        width = max(1, stdscr.getmaxyx()[1] - x - 1)
        stdscr.addnstr(y, x, text, width, attr)
    except curses.error:
        pass


def _line(stdscr, y, text, attr=0):
    try:
        stdscr.addnstr(y, 0, text, max(1, stdscr.getmaxyx()[1] - 1), attr)
    except curses.error:
        pass


def _confirm(stdscr, prompt):
    h, _ = stdscr.getmaxyx()
    stdscr.nodelay(False)
    try:
        _line(stdscr, h // 2, prompt + " ", curses.A_REVERSE)
        stdscr.refresh()
        key = stdscr.getch()
        return key in (ord("y"), ord("Y"))
    finally:
        stdscr.nodelay(True)


def _help(stdscr):
    lines = ["Keys", "Up/Down select item or parameter; Left/Right focus or adjust", "Enter numeric edit; Escape cancels edit/returns to item list", "Tab changes page; c toggles coarse 3 dB / 0.20 steps", "m mute  h HPF  p confirmed polarity  b spatial bypass  r refresh", "Y is quad only/inactive in stereo. q quits; runtime changes are temporary.", "Press any key..."]
    stdscr.nodelay(False)
    try:
        stdscr.erase()
        for i, line in enumerate(lines): _line(stdscr, i + 1, line)
        stdscr.refresh()
        while stdscr.getch() == -1:
            pass
    finally:
        stdscr.nodelay(True)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Development-only SC-ADAT OSC terminal console")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=57120)
    args = parser.parse_args()
    client = OscClient(args.host, args.port)
    model = ConsoleModel(client)
    try:
        model.start()
        curses.wrapper(draw, model)
    except (OSError, TimeoutError, RuntimeError, ValueError) as exc:
        print(f"console unavailable: {exc}", file=sys.stderr)
        return 1
    finally:
        print("Changed runtime values (not persisted):")
        for key, value in sorted(model.summary().items()): print(f"  {key}={value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
