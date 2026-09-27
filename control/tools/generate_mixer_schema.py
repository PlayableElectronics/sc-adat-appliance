#!/usr/bin/env python3
"""Export the validated mixer runtime model for all control surfaces."""

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "mixer"))

from contract import CONTRACT, CONTRACT_VERSION, GROUPS, source_controls_for_mode  # noqa: E402
from mixerctl import controls as runtime_controls  # noqa: E402
from mixerctl import group_limits, read_config  # noqa: E402

CONFIG_PATH = ROOT / "payload/config/mixer.conf"
OUTPUT_PATH = ROOT / "control/generated/mixer-schema.json"


def amplitude_db(value):
    return -120.0 if value <= 0 else 20.0 * math.log10(value)


def resolved_control(definition, key, label, default):
    value_type = definition["value_type"]
    bounds = definition.get("range", {})
    item = {"key": key, "label": label, "value_type": value_type,
            "unit": definition["unit"], "display": definition["display"],
            "default": default}
    if value_type == "amplitude":
        item["range"] = {"min": bounds["min"], "max": bounds["max"],
                         "display_min": amplitude_db(bounds["min"]),
                         "display_max": amplitude_db(bounds["max"])}
        item["step"] = (definition.get("increments") or {}).get("fine", 0.5)
    elif "values" in bounds:
        item["range"] = {"values": bounds["values"]}
    else:
        item["range"] = {"min": bounds["min"], "max": bounds["max"]}
        if "enumerated_steps" in definition:
            item["range"]["values"] = definition["enumerated_steps"]
        else:
            item["step"] = 0.01 if value_type == "normalized" else 1
    return item


def build_schema(config_path=CONFIG_PATH):
    values, channels = read_config(str(config_path))
    state = dict(runtime_controls(values, channels))
    definitions = {item["key_template"]: item for item in CONTRACT["controls"]}
    exported_controls = []
    pages = [{"id": "master", "label": "MASTER", "controls": []}]

    def add(page, definition, key, label):
        exported_controls.append(resolved_control(definition, key, label, state[key]))
        page["controls"].append(key)

    add(pages[0], definitions["master"], "master", "Master level")

    groups = []
    for index, name in enumerate(GROUPS):
        limits = group_limits(values, name)
        groups.append({"index": index, "id": name, "name": name,
                       "limits": {"x": [limits[0], limits[1]],
                                  "y": [limits[2], limits[3]],
                                  "width": [limits[4], limits[5]]}})
        page = {"id": f"group.{name}", "label": name.upper(), "controls": []}
        add(page, definitions["groupLevelN"], f"groupLevel{index}", "Level")
        pages.append(page)

    sources = []
    for index, source in enumerate(values["_sources"]):
        snapshot = source.snapshot()
        snapshot["index"] = index
        sources.append(snapshot)
        page = {"id": f"source.{source.id}", "label": source.name.upper(), "controls": []}
        for definition in source_controls_for_mode(source.mode):
            key = definition["key_template"].replace("N", str(index))
            add(page, definition, key, definition["label"])
        pages.append(page)

    return {"schema_version": "1", "contract_version": CONTRACT_VERSION,
            "generated_from": {"runtime_config": "payload/config/mixer.conf",
                               "control_contract": "control/mixer-control-contract.json"},
            "groups": groups, "sources": sources,
            "controls": exported_controls, "pages": pages}


def render(schema):
    return json.dumps(schema, indent=2) + "\n"


def generate(output_path=OUTPUT_PATH, check=False):
    content = render(build_schema())
    if check:
        if not output_path.is_file() or output_path.read_text(encoding="utf-8") != content:
            raise SystemExit("stale generated schema: run ./lab control generate norns")
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
    return len(json.loads(content)["controls"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    count = generate(check=args.check)
    print(f"{'verified' if args.check else 'generated'} {OUTPUT_PATH.relative_to(ROOT)} ({count} controls)")
