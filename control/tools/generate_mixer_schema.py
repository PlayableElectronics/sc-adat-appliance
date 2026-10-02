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
            "default": default, "writable": definition.get("writable", True)}
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

    for definition in CONTRACT["controls"]:
        if definition["scope"] == "master":
            key=definition["key_template"]
            add(pages[0], definition, key, definition["label"])

    groups = []
    for index, name in enumerate(GROUPS):
        limits = group_limits(values, name)
        groups.append({"index": index, "id": name, "name": name,
                       "limits": {"x": [limits[0], limits[1]],
                                  "y": [limits[2], limits[3]],
                                  "width": [limits[4], limits[5]]}})
        page = {"id": f"group.{name}", "label": name.upper(), "controls": []}
        for definition in CONTRACT["controls"]:
            if definition["scope"] == "group":
                key=definition["key_template"].replace("N",str(index))
                resolved=dict(definition)
                if definition.get("range",{}).get("source","").startswith("group_limits"):
                    dimension=definition["range"]["source"].rsplit(".",1)[-1]
                    resolved["range"]={"min":groups[index]["limits"][dimension][0],"max":groups[index]["limits"][dimension][1]}
                add(page,resolved,key,definition["label"])
        pages.append(page)

    for scope,page_id,label in (("recorder","recording","RECORDING"),("recorder_status","recording","RECORDING"),("generator","diagnostics","PROTECTED TEST GENERATOR")):
        controls_for_page=[item for item in CONTRACT["controls"] if item["scope"]==scope]
        if not controls_for_page: continue
        page=next((item for item in pages if item["id"]==page_id),None)
        if page is None:
            page={"id":page_id,"label":label,"controls":[]}; pages.append(page)
        for definition in controls_for_page:
            add(page,definition,definition["key_template"],definition["label"])

    sources = []
    for index, source in enumerate(values["_sources"]):
        snapshot = source.snapshot()
        snapshot["index"] = index
        sources.append(snapshot)

    source_by_input = {physical: (index, source) for index, source in enumerate(values["_sources"])
                       for physical in source.inputs}
    mapping_definitions = {item["key_template"]: item for item in CONTRACT["mapping_controls"]}
    for physical in range(1, 17):
        source_index, source = source_by_input[physical]
        page = {"id": f"input.{physical}", "label": f"INPUT {physical}: {source.name}",
                "controls": [], "physical_input": physical, "source_index": source_index,
                "source_id": source.id, "source_name": source.name, "source_mode": source.mode,
                "source_inputs": list(source.inputs), "source_group": source.group,
                "processing_linked": source.mode == "stereo",
                "meters": {"left": f"input.{physical}.left", "right": f"input.{physical}.right"}}
        for definition in mapping_definitions.values():
            key = definition["key_template"].replace("N", str(physical - 1))
            add(page, definition, key, definition["label"])
        if physical == source.inputs[0]:
            for definition in source_controls_for_mode(source.mode):
                key = definition["key_template"].replace("N", str(source_index))
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
