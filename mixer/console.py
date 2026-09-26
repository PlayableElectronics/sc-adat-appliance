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

from mixerctl import GROUPS, METER_WIDTH, dbamp, group_limits, packet, parse_packet, read_config, validate_parameter

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "payload/config/mixer.conf"
METER_PERIOD = 0.2
HEALTH_PERIOD = 5.0
OSC_TIMEOUT = 0.75
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
        self.sock.sendto(packet("/mixer/get-all", ","), self.address)
        state = {}
        deadline = time.monotonic() + OSC_TIMEOUT
        while time.monotonic() < deadline:
            try:
                path, _, values = parse_packet(self.sock.recv(65535))
            except socket.timeout:
                break
            if path == "/mixer/state" and len(values) == 2:
                state[str(values[0])] = values[1]
            elif path == "/mixer/get-all-done":
                return state
        if not state:
            raise TimeoutError("OSC get-all timed out")
        return state

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


def read_health(log_path=None):
    """Read hardware/process state without creating a JACK client."""
    health = {"stale": False, "clock": {}, "jack": {}, "xruns": 0}
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
        proc = Path("/proc/asound/card0/rme9652").read_text(encoding="utf-8")
        match = re.search(r"^ADAT Sample rate:\s*(\d+)Hz", proc, re.MULTILINE)
        health["clock"]["rate"] = int(match.group(1)) if match else None
    except OSError:
        health["clock"]["rate"] = None
    for entry in Path("/proc").iterdir():
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
    log = Path(log_path) if log_path else ROOT / ".local/sc-audio-logs/jack.log"
    try:
        text = log.read_text(encoding="utf-8", errors="replace")
        health["xruns"] = len(re.findall(r"xrun|process error|underrun|overrun", text, re.I))
    except OSError:
        health["xruns"] = 0
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

    def _range(self, key):
        if key.startswith("trim"):
            return TRIM_MIN_DB, TRIM_MAX_DB
        if key.startswith(("groupLevel", "master")):
            return 0.0001, 2.0
        if key.startswith("hpfHz"):
            return 20.0, 20000.0
        if key.endswith("SpatialBypass"):
            return 0.0, 1.0
        if key.endswith("PosX") or key.endswith("PosY") or key.endswith("Width"):
            index = int(key[5:key.index("Pos")] if "Pos" in key else key[5:key.index("Width")])
            limits = group_limits(self.values, self.groups[index])
            if key.endswith("PosX"): return limits[0], limits[1]
            if key.endswith("PosY"): return limits[2], limits[3]
            return limits[4], limits[5]
        return None

    def validate(self, key, value):
        if key.endswith("PosY"):
            raise ValueError("Y is quad only / inactive in stereo")
        if key.startswith("trim"):
            return dbamp(float(value))
        return validate_parameter(key, value, self.values)

    def write(self, key, value, confirm=None):
        value = self.validate(key, value)
        old = self.state.get(key)
        if key == "master" and old is not None and value > float(old):
            if confirm is None or not confirm(f"Increase master {db(old)} dB -> {db(value)} dB? y/N"):
                self.message = "master increase cancelled"
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

    def bool_toggle(self, key, confirm=None):
        return self.write(key, 0 if int(float(self.state.get(key, 0))) else 1, confirm)

    def summary(self):
        return dict(self.changed)


CHANNEL_FIELDS = ("trim", "mute", "polarity", "hpf", "hpfHz")
GROUP_FIELDS = ("level", "x", "y", "width", "bypass")


def channel_key(row, field):
    return f"{field}{row}"


def group_key(row, field):
    return {"level": f"groupLevel{row}", "x": f"group{row}PosX", "y": f"group{row}PosY", "width": f"group{row}Width", "bypass": f"group{row}SpatialBypass"}[field]


def _value_text(value, gain=False):
    if gain:
        return f"{db(value)} dB"
    return str(value)


def draw(stdscr, model):
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.keypad(True)
    while True:
        now = time.monotonic()
        model.refresh(now)
        stdscr.erase()
        h, w = stdscr.getmaxyx()
        title = {1: "CHANNELS", 2: "GROUPS", 3: "MASTER / STATUS"}[model.page]
        _line(stdscr, 0, f"SC-ADAT development console  [{title}]  (q quit, ? help, r refresh)", curses.A_BOLD)
        if model.page == 1:
            _draw_channels(stdscr, model)
        elif model.page == 2:
            _draw_groups(stdscr, model)
        else:
            _draw_status(stdscr, model)
        footer = f"{model.message} | Up/Down row Tab field Left/Right adjust Space toggle +/- gain p polarity | 1/2/3 pages"
        _line(stdscr, h - 1, footer[-max(1, w - 1):])
        stdscr.refresh()
        key = stdscr.getch()
        if key == -1:
            time.sleep(0.03)
            continue
        if key in (ord("q"), ord("Q")):
            return
        if key == ord("?"):
            _help(stdscr)
            continue
        if key in (ord("1"), ord("2"), ord("3")):
            model.page = int(chr(key)); model.row = 0; model.field = 0; continue
        if key == ord("r"):
            try:
                model.state.update(model.client.get_all()); model.refresh(force=True); model.message = "complete state refreshed"
            except Exception as exc:
                model.message = f"refresh failed; audio untouched: {exc}"
            continue
        if key in (curses.KEY_UP, curses.KEY_DOWN):
            model.row = max(0, min(_row_count(model), model.row + (1 if key == curses.KEY_DOWN else -1))); continue
        if key == 9:
            model.field = (model.field + 1) % len(CHANNEL_FIELDS if model.page == 1 else GROUP_FIELDS if model.page == 2 else ("master",)); continue
        try:
            _handle_key(model, key, stdscr)
        except ValueError as exc:
            model.message = str(exc)


def _row_count(model):
    return (15 if model.page == 1 else 7 if model.page == 2 else 0)


def _handle_key(model, key, stdscr):
    confirm = lambda prompt: _confirm(stdscr, prompt)
    if model.page == 1:
        field = CHANNEL_FIELDS[model.field % len(CHANNEL_FIELDS)]; keyname = channel_key(model.row, field)
        if field == "polarity" and key == ord("p"):
            return model.write(keyname, -1 if int(float(model.state.get(keyname, 1))) == 1 else 1, confirm)
        if field in ("mute", "hpf") and key == ord(" "):
            return model.bool_toggle(keyname)
        if field == "trim" and key in (ord("+"), ord("-")):
            return model.gain_adjust(keyname, GAIN_STEP_DB if key == ord("+") else -GAIN_STEP_DB, confirm)
        if field == "trim" and key in (curses.KEY_LEFT, curses.KEY_RIGHT, ord("["), ord("]")):
            return model.gain_adjust(keyname, GAIN_STEP_DB if key in (curses.KEY_RIGHT, ord("]")) else -GAIN_STEP_DB, confirm)
        if field == "hpfHz" and key in (curses.KEY_LEFT, curses.KEY_RIGHT, ord("["), ord("]")):
            return model.write(keyname, float(model.state.get(keyname, 80)) + (10 if key in (curses.KEY_RIGHT, ord("]")) else -10))
    elif model.page == 2:
        field = GROUP_FIELDS[model.field % len(GROUP_FIELDS)]; keyname = group_key(model.row, field)
        if field == "bypass" and key == ord(" "):
            return model.bool_toggle(keyname)
        if field == "level" and key in (ord("+"), ord("-"), curses.KEY_LEFT, curses.KEY_RIGHT, ord("["), ord("]")):
            return model.gain_adjust(keyname, GAIN_STEP_DB if key in (ord("+"), curses.KEY_RIGHT, ord("]")) else -GAIN_STEP_DB, confirm)
        if field in ("x", "y", "width") and key in (curses.KEY_LEFT, curses.KEY_RIGHT, ord("["), ord("]")):
            if field == "y": raise ValueError("Y is quad only / inactive in stereo")
            return model.write(keyname, float(model.state.get(keyname, 0.5)) + (0.05 if key in (curses.KEY_RIGHT, ord("]")) else -0.05))
    else:
        if key in (ord("+"), ord("-"), curses.KEY_LEFT, curses.KEY_RIGHT, ord("["), ord("]")):
            return model.gain_adjust("master", GAIN_STEP_DB if key in (ord("+"), curses.KEY_RIGHT, ord("]")) else -GAIN_STEP_DB, confirm)


def _draw_channels(stdscr, model):
    _line(stdscr, 1, "# name                 group       peak/rms       trim(-80..+12) mute pol hpf HPFHz [field: %s]" % CHANNEL_FIELDS[model.field % 5])
    meters = model.meters or {"input_peak": [0] * 16, "input_rms": [0] * 16}
    for i, row in enumerate(model.channels):
        peak = db(meters["input_peak"][i]); rms = db(meters["input_rms"][i])
        text = f"{i+1:02d} {row['name'][:20]:20s} {row['group'][:10]:10s} {peak:>6}/{rms:<6} {db(model.state.get(f'trim{i}', 1)):>6} {int(float(model.state.get(f'mute{i}', 0)))}   {int(float(model.state.get(f'polarity{i}', 1))):+d}   {int(float(model.state.get(f'hpf{i}', 0)))}  {float(model.state.get(f'hpfHz{i}', row['hpf_hz'])):6.0f}"
        _line(stdscr, i + 2, (">" if i == model.row else " ") + text)


def _draw_groups(stdscr, model):
    _line(stdscr, 1, "group       peak/rms       level     X       Y(inactive) width(active) bypass  allowed X/Y/W ranges")
    meters = model.meters or {"group_peak": [0] * 8, "group_rms": [0] * 8}
    for i, name in enumerate(GROUPS):
        y = float(model.state.get(f"group{i}PosY", 0.5))
        limits = group_limits(model.values, name)
        text = f"{name:10s} {db(meters['group_peak'][i]):>6}/{db(meters['group_rms'][i]):<6} {db(model.state.get(f'groupLevel{i}', 1)):>7} {float(model.state.get(f'group{i}PosX', .5)):.2f}  {y:.2f} inactive  {float(model.state.get(f'group{i}Width', .5)):.2f}    {int(float(model.state.get(f'group{i}SpatialBypass', 0)))}  {limits[0]:.2f}..{limits[1]:.2f}/{limits[2]:.2f}..{limits[3]:.2f}/{limits[4]:.2f}..{limits[5]:.2f}"
        _line(stdscr, i + 2, (">" if i == model.row else " ") + text)


def _draw_status(stdscr, model):
    meters = model.meters or {"output_peak": [0] * 16, "output_rms": [0] * 16}
    age = "stale" if model.stale() else f"{time.monotonic() - model.meter_time:.1f}s old"
    _line(stdscr, 1, f"outputs L {db(meters['output_peak'][0])}/{db(meters['output_rms'][0])} dBFS  R {db(meters['output_peak'][1])}/{db(meters['output_rms'][1])} dBFS  meters {age}")
    master = model.state.get("master", 0)
    _line(stdscr, 3, f"master {float(master):.9f} ({db(master)} dB)  +/- 0.5 dB steps; increases confirm")
    clock = model.health.get("clock", {})
    jack = model.health.get("jack", {})
    _line(stdscr, 5, f"RME {clock.get('mode','?')} source={clock.get('source','?')} ADAT1={clock.get('adat1','?')} ADAT2={clock.get('adat2','?')} ADAT3={clock.get('adat3','?')} rate={clock.get('rate','?')}")
    _line(stdscr, 6, f"JACK device={jack.get('device','?')} rate={jack.get('rate','?')} period={jack.get('period','?')} periods={jack.get('periods','?')} RT={jack.get('rt','?')} xruns={model.health.get('xruns','?')}")
    _line(stdscr, 8, "Mixer state is read through OSC; health is read-only and sampled no faster than every 5 seconds.")


def _line(stdscr, y, text, attr=0):
    try:
        stdscr.addnstr(y, 0, text, max(1, stdscr.getmaxyx()[1] - 1), attr)
    except curses.error:
        pass


def _confirm(stdscr, prompt):
    h, w = stdscr.getmaxyx(); _line(stdscr, h // 2, prompt + " ", curses.A_REVERSE); stdscr.refresh()
    key = stdscr.getch()
    return key in (ord("y"), ord("Y"))


def _help(stdscr):
    lines = ["Keys", "Up/Down row  Tab editable field  Left/Right or [/ ] adjust", "+/- gain by 0.5 dB  Space toggle Boolean  p confirmed polarity", "1 Channels  2 Groups  3 Master/Status  r full refresh  q quit", "Y is inactive in stereo. Changes are runtime-only and are printed on exit.", "Press any key..."]
    stdscr.erase()
    for i, line in enumerate(lines): _line(stdscr, i + 1, line)
    stdscr.refresh(); stdscr.getch()


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
