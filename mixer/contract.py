"""Versioned mixer control contract shared by runtime tooling and clients."""
import json
import re
from pathlib import Path

CONTRACT_PATH = Path(__file__).resolve().parents[1] / "control/mixer-control-contract.json"


def load_contract(path=CONTRACT_PATH):
    return json.loads(Path(path).read_text(encoding="utf-8"))


CONTRACT = load_contract()
CONTRACT_VERSION = CONTRACT["contract_version"]
GROUPS = tuple(CONTRACT["groups"])


def _pattern(template):
    escaped = re.escape(template).replace("N", r"(?P<index>\d+)")
    return re.compile(r"^" + escaped + r"$")


def control_definitions():
    return tuple(CONTRACT["controls"])


def source_control_definitions():
    return tuple(CONTRACT.get("source_controls", ()))


def source_controls_for_mode(mode):
    return tuple(item for item in source_control_definitions() if mode in item["modes"])


def source_contract(sources):
    """Build the dynamic source portion without duplicating its schema."""
    result = []
    for index, source in enumerate(sources):
        controls = []
        for definition in source_controls_for_mode(source.mode):
            controls.append({"key": definition["key_template"].replace("N", str(index)),
                             "label": definition["label"], "value_type": definition["value_type"],
                             "unit": definition["unit"], "display": definition["display"],
                             "range": definition["range"]})
        left, right = source.inputs[0], source.inputs[-1]
        result.append({"index": index, **source.snapshot(), "controls": controls,
                       "meters": {"left": {"id": f"input.{left}.left", "physical_input": left, "peak_index": left - 1, "rms_index": 16 + left - 1},
                                  "right": {"id": f"input.{right}.right", "physical_input": right, "peak_index": right - 1, "rms_index": 16 + right - 1}}})
    inputs = []
    for physical in range(1, 17):
        source = next(item for item in sources if physical in item.inputs)
        stereo = source.mode == "stereo"
        inputs.append({"physical_input": physical, "source_id": source.id,
                       "source_name": source.name, "mode": source.mode,
                       "partner": source.inputs[1] if stereo and physical == source.inputs[0]
                                  else source.inputs[0] if stereo else 0,
                       "orientation": "left" if stereo and physical == source.inputs[0]
                                      else "right" if stereo else "mono",
                       "group": source.group,
                       "controls": [item["key_template"] for item in source_controls_for_mode(source.mode)]})
    return {"contract_version": CONTRACT_VERSION, "source_map_version": CONTRACT["source_map"]["version"],
            "sources": result, "inputs": inputs,
            "mapping_controls": CONTRACT.get("mapping_controls", ())}


def control_for_key(key):
    for definition in control_definitions():
        match = _pattern(definition["key_template"]).match(str(key))
        if match:
            return definition, (int(match.group("index")) if "index" in match.groupdict() else None)
    return None, None


def controls_for_scope(scope, mode=None):
    result = [item for item in control_definitions() if item["scope"] == scope]
    if mode:
        result = [item for item in result if mode in item["modes"]]
    return sorted(result, key=lambda item: item["presentation_order"])
