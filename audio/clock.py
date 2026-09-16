#!/usr/bin/env python3
"""Stable-name ALSA clock control for the Debian RME DIGI9652 boundary."""
import argparse, os, re, subprocess, sys

CARD = "Digi9652"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPOSE = os.environ.get("COMPOSE", f"docker compose -f {ROOT}/containers/sc-development/compose.yaml")
MODE_NAMES = {"master": "Master", "autosync": "AutoSync", "wordclock": "Word Clock"}
SOURCE_NAMES = {"adat1": "ADAT1 In", "adat2": "ADAT2 In", "adat3": "ADAT3 In", "iec958": "IEC958 In"}
STATE_NAMES = {"No Lock": "No Lock", "Lock": "Lock but not Sync", "No Lock Sync": "No Lock", "Lock Sync": "Lock Sync"}

def command(args, check=True):
    return subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=check).stdout
def parse_control(text):
    items = {int(n): name for n, name in re.findall(r"Item #(\d+) '([^']+)'", text)}
    match = re.search(r"^\s*: values=([-+]?\d+)", text, re.MULTILINE)
    if not match: raise ValueError("ALSA control has no value")
    index = int(match.group(1))
    return {"index": index, "raw": items.get(index, f"item-{index}"), "value": index, "items": items}
def control(name):
    return parse_control(command(["amixer", "-c", CARD, "cget", f"name={name}"]))
def set_control(name, value):
    command(["amixer", "-c", CARD, "cset", f"name={name}", value])
def declared():
    result = {}
    with open(os.path.join(ROOT, "audio", "clock.conf"), encoding="utf-8") as stream:
        for line in stream:
            line=line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value=line.split("=", 1); result[key.strip()]=value.strip()
    if result.get("mode") not in MODE_NAMES or int(result.get("sample_rate", "0")) != 48000:
        raise ValueError("audio/clock.conf must declare mode=master and sample_rate=48000")
    return result
def declared_mode():
    try:
        with open(os.path.join(ROOT, "audio", "clock.conf"), encoding="utf-8") as stream:
            for line in stream:
                key, _, value = line.partition("=")
                if key.strip() == "mode": return MODE_NAMES.get(value.strip(), value.strip())
    except OSError:
        pass
    return "unknown"
def jack_rate():
    try:
        output=command(COMPOSE.split() + ["exec", "-T", "sc-audio", "jack_samplerate"])
        match=re.search(r"(\d+(?:\.\d+)?)", output)
        return int(float(match.group(1))) if match else None
    except (OSError, subprocess.CalledProcessError):
        return None
def services_running():
    try:
        names=command(COMPOSE.split() + ["ps", "--status", "running", "--services"]).split()
        return {name for name in names if name in ("sc-audio", "sc-mixer")}
    except (OSError, subprocess.CalledProcessError):
        return set()
def service_stop(): command(COMPOSE.split() + ["stop", "sc-mixer", "sc-audio"], check=False)
def service_start(running):
    if "sc-mixer" in running: command(COMPOSE.split() + ["up", "-d", "sc-audio", "sc-mixer"])
    elif "sc-audio" in running: command(COMPOSE.split() + ["up", "-d", "sc-audio"])
def status():
    mode=control("Sync Mode"); source=control("Preferred Sync Source")
    adats={name: control(f"{name.upper()} Sync Check") for name in ("adat1", "adat2", "adat3")}
    iec=control("IEC958 Sample Rate"); rate=jack_rate()
    mode_name=mode["raw"]; source_name=source["raw"]
    print(f"card: {CARD} (stable ALSA name)")
    print(f"configured mode: {declared_mode()}")
    print(f"observed mode: {mode_name}")
    print(f"effective direction: {'internal master' if mode_name == 'Master' else 'external slave'}")
    print(f"preferred external source: {source_name}")
    for name, value in adats.items():
        suffix=" (physically unavailable on this installation)" if name == "adat3" else ""
        print(f"{name.upper()}: {STATE_NAMES.get(value['raw'], value['raw'])} [raw: {value['raw']}]" + suffix)
    print(f"IEC958: {iec['value']} Hz" if iec["value"] > 0 else "IEC958: unavailable/error")
    print(f"JACK sample rate: {rate if rate is not None else 'not running'}")
    healthy = mode_name == "Master" and (rate in (None, 48000))
    if mode_name == "AutoSync": healthy = STATE_NAMES.get(adats.get(source_name.lower().replace(" in", ""), {}).get("raw"), "") == "Lock Sync" and rate in (None, 48000)
    if mode_name == "Word Clock": healthy = False
    if mode_name == "Word Clock": conclusion="UNHEALTHY: Word Clock selected; no usable word-clock lock/control is exposed on this installation"
    elif mode_name == "AutoSync" and not healthy: conclusion="UNHEALTHY: external source is not Lock Sync"
    else: conclusion="HEALTHY: internal 48 kHz master" if healthy else "UNHEALTHY: JACK rate or clock mode mismatch"
    print(f"health: {conclusion}")
    return 0 if healthy else 1
def set_mode(mode, source=None):
    if mode not in MODE_NAMES: raise ValueError("mode must be master, autosync, or wordclock")
    if mode == "autosync" and source not in SOURCE_NAMES or mode != "autosync" and source is not None:
        raise ValueError("autosync requires --source adat1|adat2|adat3|iec958; other modes do not accept a source")
    old_mode=control("Sync Mode")["raw"]; old_source=control("Preferred Sync Source")["raw"]; running=services_running(); before_rate=jack_rate()
    if before_rate not in (None, 48000): raise RuntimeError("JACK is not at the required 48 kHz before clock change")
    if running: service_stop()
    try:
        set_control("Sync Mode", MODE_NAMES[mode])
        if mode == "autosync": set_control("Preferred Sync Source", SOURCE_NAMES[source])
        new_mode=control("Sync Mode")["raw"]; new_source=control("Preferred Sync Source")["raw"]
        if new_mode != MODE_NAMES[mode] or (mode == "autosync" and new_source != SOURCE_NAMES[source]):
            raise RuntimeError("ALSA clock readback differs from requested values")
    except Exception:
        try: set_control("Sync Mode", old_mode); set_control("Preferred Sync Source", old_source)
        finally: service_start(running)
        rollback="./lab audio clock set " + ("autosync --source " + old_source.lower().replace(" in", "") if old_mode == "AutoSync" else old_mode.lower().replace(" ", ""))
        print(f"clock change rolled back; rollback command: {rollback}", file=sys.stderr)
        raise
    service_start(running)
    after_rate=jack_rate()
    if after_rate not in (None, 48000):
        raise RuntimeError(f"JACK sample rate changed unexpectedly to {after_rate}")
    print(f"clock mode readback: {new_mode}; preferred source: {new_source}")
    if mode == "master": print("connected equipment must slave to ADAT")
    if mode == "autosync":
        print("external synchronization is healthy only when the selected source reports Lock Sync")
        return status()
    if mode == "wordclock": return status()
    return 0
def main():
    parser=argparse.ArgumentParser(); sub=parser.add_subparsers(dest="action", required=True)
    sub.add_parser("status"); apply_parser=sub.add_parser("apply"); set_parser=sub.add_parser("set"); set_parser.add_argument("mode", choices=MODE_NAMES); set_parser.add_argument("--source")
    args=parser.parse_args()
    try:
        if args.action == "status": return status()
        if args.action == "apply": return set_mode(declared()["mode"])
        return set_mode(args.mode, args.source)
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"audio-clock: {exc}", file=sys.stderr); return 1
if __name__ == "__main__": sys.exit(main())
