#!/usr/bin/env python3
"""Generate the data-only norns control table from the mixer contract."""

import json
import math
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
CONTRACT_PATH = ROOT / "control" / "mixer-control-contract.json"
MIXER_CONFIG_PATH = ROOT / "payload" / "config" / "mixer.conf"
OUTPUT_PATH = ROOT / "control" / "norns" / "lib" / "mixer_contract.lua"


def lua(value):
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, list):
        return "{" + ", ".join(lua(item) for item in value) + "}"
    raise TypeError(type(value))


def amplitude_db(value):
    return -120.0 if value <= 0 else 20.0 * math.log10(value)


def source_map(path=MIXER_CONFIG_PATH):
    values = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        if separator:
            values[key.strip()] = value.strip()
    if values.get("source_map_version") != "1":
        raise ValueError("norns generator requires source_map_version=1")
    count = int(values["source.count"])
    sources = []
    for index in range(1, count + 1):
        prefix = f"source.{index}."
        source = {field: values[prefix + field] for field in ("id", "name", "mode", "inputs", "group")}
        source["inputs"] = [int(item) for item in source["inputs"].split(",")]
        sources.append(source)
    return sources


def expanded_controls(contract, sources=None):
    if sources is None:
        sources = source_map()
    groups = contract["groups"]
    controls = []
    pages = [{"label": "MASTER", "controls": []}]
    group_pages = []
    source_pages = []

    definitions = {item["key_template"]: item for item in contract["controls"]}

    def add(page, definition, key, label):
        value_type = definition["value_type"]
        item = {"key": key, "label": label, "kind": value_type}
        bounds = definition.get("range", {})
        if value_type == "amplitude":
            item.update({
                "kind": "db",
                "min": amplitude_db(bounds["min"]),
                "max": amplitude_db(bounds["max"]),
                "step": (definition.get("increments") or {}).get("fine", 0.5),
            })
        elif value_type == "boolean":
            item["values"] = [0, 1]
        elif value_type == "enum":
            item["values"] = bounds["values"]
        elif value_type == "frequency":
            if "enumerated_steps" in definition:
                item["values"] = definition["enumerated_steps"]
            else:
                item.update({"min": bounds["min"], "max": bounds["max"], "step": 1})
        elif value_type == "normalized":
            item.update({"min": bounds["min"], "max": bounds["max"], "step": 0.01})
        else:
            raise ValueError(f"unsupported safe norns type: {value_type}")
        controls.append(item)
        page["controls"].append(key)

    master = definitions["master"]
    add(pages[0], master, "master", "Master level")

    group_level = definitions["groupLevelN"]
    for index, name in enumerate(groups):
        page = {"label": name.upper(), "controls": []}
        add(page, group_level, f"groupLevel{index}", "Level")
        group_pages.append(page)

    source_definitions = contract["source_controls"]
    for index, source in enumerate(sources):
        page = {"label": source["name"].upper(), "controls": []}
        for definition in source_definitions:
            if source["mode"] not in definition["modes"]:
                continue
            key = definition["key_template"].replace("N", str(index))
            add(page, definition, key, definition["label"])
        source_pages.append(page)

    pages.extend(group_pages)
    pages.extend(source_pages)
    return controls, pages


def generate():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    controls, pages = expanded_controls(contract)
    lines = [
        "-- Generated from control/mixer-control-contract.json; do not edit.",
        "return {",
        f"  version = {lua(contract['contract_version'])},",
        "  controls = {",
    ]
    for item in controls:
        fields = ", ".join(f"{key} = {lua(value)}" for key, value in item.items())
        lines.append(f"    {{{fields}}},")
    lines.extend(["  },", "  pages = {"])
    for page in pages:
        lines.append(
            "    {label = " + lua(page["label"]) + ", controls = " + lua(page["controls"]) + "},"
        )
    lines.extend(["  }", "}", ""])
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")
    return len(controls)


if __name__ == "__main__":
    count = generate()
    print(f"generated {OUTPUT_PATH.relative_to(ROOT)} ({count} writable controls)")
