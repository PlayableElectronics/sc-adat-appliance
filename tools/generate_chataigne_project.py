#!/usr/bin/env python3
"""Generate the native Chataigne 1.10.4 SC-ADAT control surface."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SEED = ROOT / "chataigne" / "Mixer.noisette"
OUT = ROOT / "control" / "chataigne" / "sc-adat-quad.noisette"
CONTRACT = json.loads((ROOT / "control/mixer-control-contract.json").read_text(encoding="utf-8"))
GROUPS = tuple(CONTRACT["groups"])


def parameter(kind, nice, short, value, minimum=None, maximum=None, description=""):
    item = {"type": kind, "niceName": nice, "shortName": short, "value": value}
    if description:
        item["description"] = description
    if minimum is not None:
        item["minValue"] = minimum
    if maximum is not None:
        item["maxValue"] = maximum
    return item


def variable(factory, kind, nice, short, value, minimum=None, maximum=None, description=""):
    # GenericControllableItem regenerates the child control address from its
    # child nice name. Keep that child name equal to the stable short name so
    # dashboard targets remain deterministic after Chataigne normalizes JSON.
    child = parameter(kind, short, short, value, minimum, maximum, description)
    return {"type": factory, "controllableType": kind, "niceName": nice,
            "shortName": short, "parameters": [child]}


def dashboard_item(factory, nice, short, address, position, size, style=None, read_only=False):
    params = [
        parameter("Boolean", "Is Visible", "isVisible", True),
        parameter("Point2D", "ViewUIPosition", "viewUIPosition", position),
        parameter("Point2D", "ViewUISize", "viewUISize", size),
    ]
    if style is not None:
        params.append(parameter("Enum", "Style", "style", style))
    if read_only:
        params.append(parameter("Boolean", "Read Only", "forceReadOnly", True))
    return {"type": factory, "niceName": nice, "shortName": short,
            "controllable": address, "parameters": params}


def group_panel(group_id, name, x, y):
    base = "/customVariables/scAdat/variables/"
    items = []

    def add(factory, nice, short, key, pos, size, style=None):
        items.append(dashboard_item(factory, nice, short, base + key + "/" + key,
                                    pos, size, style))

    add("DashboardParameterItem", f"{name} level", "level", f"groupLevel{group_id}", [12, 38], [260, 42], 0)
    add("DashboardParameterItem", "XY position", "xy", f"group{group_id}Position", [12, 88], [260, 190], 12)
    add("DashboardParameterItem", "Width", "width", f"group{group_id}Width", [12, 286], [125, 38], 0)
    add("DashboardParameterItem", "Spatial bypass", "spatialBypass", f"group{group_id}SpatialBypass", [147, 286], [125, 38], 23)
    add("DashboardParameterItem", "Neutral reset", "neutralReset", f"group{group_id}NeutralReset", [12, 334], [260, 38], 23)
    return {"type": "DashboardGroupItem", "niceName": f"{name} ({group_id})",
            "shortName": f"groupPanel{group_id}",
            "parameters": [parameter("Point2D", "ViewUIPosition", "viewUIPosition", [x, y]),
                           parameter("Point2D", "ViewUISize", "viewUISize", [286, 388])],
            "itemManager": {"items": items, "viewOffset": [0, 0], "viewZoom": 1.0}}


def main() -> None:
    project = json.loads(SEED.read_text(encoding="utf-8"))
    assert project["metaData"]["version"] == "1.10.4"
    module = project["modules"]["items"][0]
    assert module["type"] == "OSC"
    module["niceName"] = "SC-ADAT Mixer OSC"
    output = module["params"]["containers"]["oscOutputs"]["items"][0]
    output["niceName"] = "SC-ADAT Dell (editable target)"
    output["parameters"] = [{"value": "192.168.1.100", "controlAddress": "/remoteHost"},
                            {"value": 57120, "controlAddress": "/remotePort"}]
    module["scripts"] = {"items": [{
        "type": "Script", "niceName": "SC-ADAT Mixer Control", "shortName": "scAdatMixer",
        "parameters": [{"type": "File", "niceName": "File Path", "shortName": "filePath",
                        "value": "scripts/sc_adat_mixer.js"}],
    }], "viewOffset": [0, 0], "viewZoom": 1.0}

    vars_items = [
        variable("Float Parameter", "Float", "Connection state", "mixerStatus", 0.0, 0, 2, "0=current, 1=waiting, 2=stale/error"),
        variable("String Parameter", "String", "Status", "statusText", "Waiting for explicit Refresh", description="Connection and error status"),
        variable("Bool Parameter", "Boolean", "Connect / Refresh", "connectRefresh", False, description="Set true to request /mixer/get-all"),
        variable("Bool Parameter", "Boolean", "Stop Automation", "stopAutomation", False, description="Stops all Parrot and Time Machine playback"),
        variable("Bool Parameter", "Boolean", "Arm Automation", "automationArm", False, description="Explicit automation arm"),
        variable("Bool Parameter", "Boolean", "Arm Calibration", "calibrationArm", False, description="Explicit quad calibration arm"),
        variable("String Parameter", "String", "Parrot", "parrotPlaceholder", "Placeholder: arm explicitly before use", description="Future gesture capture/replay"),
        variable("String Parameter", "String", "Time Machine", "timeMachinePlaceholder", "Placeholder: explicit cue only", description="Future sequence control"),
    ]
    for i, name in enumerate(GROUPS):
        vars_items.extend([
            variable("Float Parameter", "Float", f"{name} level", f"groupLevel{i}", 1.0, 0, 2, f"{name} group {i} level"),
            variable("Point2D Parameter", "Point2D", f"{name} XY", f"group{i}Position", [0.5, 0.5], [0, 0], [1, 1], "X 0=left..1=right; Y 0=rear..1=front"),
            variable("Float Parameter", "Float", f"{name} width", f"group{i}Width", 0.5, 0, 1, f"{name} width"),
            variable("Bool Parameter", "Boolean", f"{name} spatial bypass", f"group{i}SpatialBypass", False),
            variable("Bool Parameter", "Boolean", f"{name} neutral reset", f"group{i}NeutralReset", False, description="Momentary reset request"),
        ])
    for n, output_name in enumerate(("front-left", "front-right", "rear-left", "rear-right")):
        vars_items.extend([
            variable("Float Parameter", "Float", f"{output_name} gain dB", f"quadOutput{n}GainDb", 0.0, -120, 24, output_name),
            variable("Bool Parameter", "Boolean", f"{output_name} mute", f"quadOutput{n}Mute", False),
            variable("Int Parameter", "Int", f"{output_name} polarity", f"quadOutput{n}Polarity", 1, -1, 1),
        ])
    vars_items.extend([
        variable("Float Parameter", "Float", "Master", "master", 1.0, 0, 2),
        variable("String Parameter", "String", "Routing mode", "routingMode", "direct", description="Read-only configuration status"),
    ])
    project["customVariables"] = {"items": [{
        "type": "CVGroup", "niceName": "SC-ADAT Controls", "shortName": "scAdat",
        "params": {"parameters": []},
        "variables": {"items": vars_items, "viewOffset": [0, 0], "viewZoom": 1.0},
        "presets": {"viewOffset": [0, 0], "viewZoom": 1.0},
    }], "viewOffset": [0, 0], "viewZoom": 1.0}

    group_panels = [group_panel(i, name, (i % 4) * 310, (i // 4) * 420)
                    for i, name in enumerate(GROUPS)]
    base = "/customVariables/scAdat/variables/"
    global_items = [
        dashboard_item("DashboardParameterItem", "Connection state", "mixerStatus", base + "mixerStatus/mixerStatus", [20, 30], [250, 40], 0, True),
        dashboard_item("DashboardParameterItem", "Status", "statusText", base + "statusText/statusText", [20, 80], [760, 40], 2, True),
        dashboard_item("DashboardParameterItem", "Connect / Refresh", "connectRefresh", base + "connectRefresh/connectRefresh", [20, 140], [240, 48], 23),
        dashboard_item("DashboardParameterItem", "Stop Automation", "stopAutomation", base + "stopAutomation/stopAutomation", [280, 140], [240, 48], 23),
        dashboard_item("DashboardParameterItem", "Arm Automation", "automationArm", base + "automationArm/automationArm", [540, 140], [240, 48], 23),
        dashboard_item("DashboardParameterItem", "Arm Calibration", "calibrationArm", base + "calibrationArm/calibrationArm", [20, 210], [240, 48], 23),
        dashboard_item("DashboardParameterItem", "Parrot (placeholder)", "parrotPlaceholder", base + "parrotPlaceholder/parrotPlaceholder", [280, 210], [300, 40], 2, True),
        dashboard_item("DashboardParameterItem", "Time Machine (placeholder)", "timeMachinePlaceholder", base + "timeMachinePlaceholder/timeMachinePlaceholder", [20, 270], [300, 40], 2, True),
    ]
    calibration_items = []
    for n, output_name in enumerate(("front-left", "front-right", "rear-left", "rear-right")):
        ox, oy = (n % 2) * 330 + 20, (n // 2) * 180 + 30
        for j, (suffix, nice, style) in enumerate((("GainDb", "Gain dB", 0), ("Mute", "Mute", 23), ("Polarity", "Polarity", 0))):
            key = f"quadOutput{n}{suffix}"
            calibration_items.append(dashboard_item("DashboardParameterItem", f"{output_name} {nice}", key,
                                                     base + key + "/" + key, [ox + (j % 2) * 150, oy + (j // 2) * 58], [140, 42], style))
    project["dashboardManager"] = {"items": [
        {"type": "Dashboard", "niceName": "SC-ADAT Groups", "shortName": "performance",
         "itemManager": {"items": group_panels, "viewOffset": [0, 0], "viewZoom": 1.0}},
        {"type": "Dashboard", "niceName": "Connection and Safety", "shortName": "connection",
         "itemManager": {"items": global_items, "viewOffset": [0, 0], "viewZoom": 1.0}},
        {"type": "Dashboard", "niceName": "Quad Output Calibration (armed)", "shortName": "calibration",
         "itemManager": {"items": calibration_items, "viewOffset": [0, 0], "viewZoom": 1.0}},
    ], "viewOffset": [0, 0], "viewZoom": 1.0}
    project["projectSettings"]["containers"]["dashboardSettings"]["parameters"][0].update({"value": "true", "enabled": True})
    OUT.write_text(json.dumps(project, separators=(",", ":")) + "\n", encoding="utf-8")
    print(OUT)


if __name__ == "__main__":
    main()
