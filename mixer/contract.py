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
