#!/usr/bin/env python3
"""Mechanically render the exported mixer schema as a Norns Lua table."""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCHEMA_PATH = ROOT / "control/generated/mixer-schema.json"
OUTPUT_PATH = ROOT / "control/norns/lib/mixer_contract.lua"

def lua(value):
    if isinstance(value, bool): return "true" if value else "false"
    if isinstance(value, (int, float)): return repr(value)
    if isinstance(value, str): return json.dumps(value)
    if isinstance(value, list): return "{" + ", ".join(lua(item) for item in value) + "}"
    raise TypeError(type(value))

def norns_control(item):
    value_type, bounds = item["value_type"], item["range"]
    result = {"key": item["key"], "label": item["label"], "kind": value_type}
    if value_type == "amplitude":
        result.update({"kind": "db", "min": bounds["display_min"], "max": bounds["display_max"], "step": item["step"]})
    elif "values" in bounds:
        result["values"] = bounds["values"]
    else:
        result.update({"min": bounds["min"], "max": bounds["max"], "step": item.get("step", 1)})
    return result

def render(schema):
    controls = [norns_control(item) for item in schema["controls"]]
    lines = ["-- Generated from control/generated/mixer-schema.json; do not edit.", "return {",
             f"  version = {lua(schema['contract_version'])},", "  controls = {"]
    for item in controls:
        fields = ", ".join(f"{key} = {lua(value)}" for key, value in item.items())
        lines.append(f"    {{{fields}}},")
    lines.extend(["  },", "  pages = {"])
    for page in schema["pages"]:
        lines.append("    {label = " + lua(page["label"]) + ", controls = " + lua(page["controls"]) + "},")
    lines.extend(["  }", "}", ""])
    return "\n".join(lines), len(controls)

def generate(output_path=OUTPUT_PATH, check=False):
    content, count = render(json.loads(SCHEMA_PATH.read_text(encoding="utf-8")))
    if check:
        if not output_path.is_file() or output_path.read_text(encoding="utf-8") != content:
            raise SystemExit("stale generated Norns table: run ./lab control generate norns")
    else:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
    return count

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    count = generate(check=args.check)
    print(f"{'verified' if args.check else 'generated'} {OUTPUT_PATH.relative_to(ROOT)} ({count} writable controls)")
