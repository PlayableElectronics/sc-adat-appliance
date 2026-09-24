#!/usr/bin/env python3
"""Generate the SC-ADAT project by extending the installed-version seed JSON."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "chataigne" / "Mixer.noisette"
OUT = ROOT / "control" / "chataigne" / "sc-adat-quad.noisette"

GROUPS = ("kick", "drums", "bass", "music_a", "music_b", "vocals", "fx_a", "fx_b")


def main() -> None:
    project = json.loads(SEED.read_text(encoding="utf-8"))
    assert project["metaData"]["version"] == "1.10.4"
    module = project["modules"]["items"][0]
    assert module["type"] == "OSC"
    module["niceName"] = "SC-ADAT Mixer OSC"
    output = module["params"]["containers"]["oscOutputs"]["items"][0]
    output["niceName"] = "SC-ADAT Dell (editable target)"
    output["parameters"] = [
        {"value": "192.168.1.100", "controlAddress": "/remoteHost"},
        {"value": 57120, "controlAddress": "/remotePort"},
    ]
    # Keep parameter names in the seed's native parameter representation. The
    # external script constructs the exact two-argument /mixer/set packets.
    for index, name in enumerate(GROUPS):
        for key, value in (
            (f"groupLevel{index}", 1.0),
            (f"group{index}PosX", 0.5),
            (f"group{index}PosY", 0.5),
            (f"group{index}Width", 0.5),
            (f"group{index}SpatialBypass", 0),
        ):
            output["parameters"].append({"value": value, "controlAddress": f"/scadat/{key}"})
    for key, value in (("master", 1.0), ("bypass", 0), ("routingMode", "direct")):
        output["parameters"].append({"value": value, "controlAddress": f"/scadat/{key}"})
    for n in range(4):
        for suffix, value in (("GainDb", 0.0), ("Mute", 0), ("Polarity", 1)):
            key = f"quadOutput{n}{suffix}"
            output["parameters"].append({"value": value, "controlAddress": f"/scadat/{key}"})
    project["projectSettings"]["containers"]["dashboardSettings"]["parameters"][0].update(
        {"value": "true", "enabled": True}
    )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(project, separators=(",", ":"), sort_keys=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
