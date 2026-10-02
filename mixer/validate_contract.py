#!/usr/bin/env python3
"""Validate the versioned control contract and its runtime integration."""
import re
from pathlib import Path

from contract import CONTRACT, CONTRACT_PATH, control_for_key, control_definitions
from mixerctl import controls, node_update, read_config, validate_parameter

ROOT = Path(__file__).resolve().parents[1]


def validate_contract():
    errors = []
    definitions = list(control_definitions())
    templates = [item["key_template"] for item in definitions]
    if len(templates) != len(set(templates)):
        errors.append("duplicate key templates")
    if not re.fullmatch(r"\d+\.\d+\.\d+", CONTRACT["contract_version"]):
        errors.append("contract_version must be semantic version")
    values, channels = read_config(str(ROOT / "payload/config/mixer.conf"))
    state = dict(controls(values, channels))
    for item in definitions:
        template = item.get("key_template", "")
        if template.count("N") > 1 or not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", template.replace("N", "0")):
            errors.append(f"malformed key template: {template}")
        if not item.get("label") or not isinstance(item.get("presentation_order"), int):
            errors.append(f"missing presentation metadata: {template}")
        modes = item.get("modes", [])
        if not modes or any(mode not in ("stereo", "quad") for mode in modes):
            errors.append(f"invalid availability: {template}")
        if template == "groupNPosY" and "stereo" in modes:
            errors.append("quad-only Y is marked stereo")
        if template.startswith(("groupNEq", "groupNComp", "groupNSat", "groupNDuck")) and modes != ["stereo"]:
            errors.append(f"stereo-only group processing has incorrect availability: {template}")
        value_range = item.get("range", {})
        if "values" in value_range and not value_range["values"]:
            errors.append(f"empty enum: {template}")
        if "min" in value_range and value_range["min"] > value_range["max"]:
            errors.append(f"reversed range: {template}")
        if item.get("writable"):
            if not item.get("dsp_mapping") and not item.get("controller_mapping"):
                errors.append(f"writable control has no DSP mapping: {template}")
            key = template.replace("N", "0")
            if key not in state:
                errors.append(f"writable control missing runtime state: {template}")
                continue
            try:
                validate_parameter(key, state[key], values)
                if not item.get("controller_mapping") and node_update(key, state[key], mode="quad") is None:
                    errors.append(f"writable control has no DSP update mapping: {template}")
            except (ValueError, KeyError, TypeError) as exc:
                errors.append(f"writable control has no validation path {template}: {exc}")
        elif item.get("readable") and template.replace("N", "0") not in state and item["scope"] != "status":
            errors.append(f"readable control missing runtime state: {template}")
    # Chataigne is an optional, currently held client. Its reference metadata
    # is intentionally not regenerated or treated as a runtime contract gate.
    return errors


if __name__ == "__main__":
    failures = validate_contract()
    if failures:
        raise SystemExit("\n".join(failures))
    print(f"PASS mixer control contract {CONTRACT['contract_version']}: {CONTRACT_PATH}")
