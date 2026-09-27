#!/usr/bin/env python3
"""Small deterministic OSC/config controller for the SC group mixers."""
import argparse, json, math, os, signal, socket, struct, sys, time

from contract import (CONTRACT_VERSION, GROUPS, control_definitions, control_for_key,
                      source_contract, source_control_definitions, source_controls_for_mode)
from source_map import AtomicSourceMap, Source, SourceMapError, validate_source_map
MAX_GROUPS = 8
SPATIAL_LIMITS = {
    "kick": (0.5, 0.5, 1.0, 1.0, 0.0, 0.0, 0.5, 1.0, 0.0),
    "drums": (0.25, 0.75, 0.5, 1.0, 0.0, 0.75, 0.5, 0.75, 0.0),
    "bass": (0.5, 0.5, 1.0, 1.0, 0.0, 0.0, 0.5, 1.0, 0.0),
    "music_a": (0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.5, 0.5, 0.5),
    "music_b": (0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.5, 0.5, 0.5),
    "vocals": (0.25, 0.75, 0.5, 1.0, 0.0, 0.5, 0.5, 1.0, 0.0),
    "fx_a": (0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.5, 0.5, 0.5),
    "fx_b": (0.0, 1.0, 0.0, 1.0, 0.0, 1.0, 0.5, 0.5, 0.5),
}
BUS_GROUP_STEMS = 52
BUS_QUAD_GROUPS = 76
BUS_PHYSICAL_OUT = 0
BUS_INPUTS = 26
BUS_RANGES = {"inputs": (BUS_INPUTS, BUS_INPUTS + 26), "group_stems": (BUS_GROUP_STEMS, BUS_GROUP_STEMS + 16), "quad_group": (BUS_QUAD_GROUPS, BUS_QUAD_GROUPS + 32), "physical_outputs": (BUS_PHYSICAL_OUT, 26)}
assert all(a[1] <= b[0] or b[1] <= a[0] for i,a in enumerate(BUS_RANGES.values()) for j,b in enumerate(BUS_RANGES.values()) if i < j)
FIELDS = ("name", "input", "output", "group", "trim_db", "mute", "polarity", "hpf", "hpf_hz")
METER_WIDTH = 16 + 16 + 8 + 8 + 16 + 16
BULK_STATE_ENTRIES = 8

def osc_string(value):
    raw = value.encode() + b"\0"; return raw + b"\0" * ((4 - len(raw) % 4) % 4)
def packet(path, types, values=()):
    out = osc_string(path) + osc_string(types)
    for typ, value in zip(types[1:], values):
        if typ == "i": out += struct.pack(">i", int(value))
        elif typ == "f": out += struct.pack(">f", float(value))
        elif typ == "s": out += osc_string(str(value))
        else: raise ValueError("unsupported OSC type")
    return out
def osc_read(data, pos=0):
    end = data.index(b"\0", pos); text = data[pos:end].decode(); return text, (end + 4) & ~3
def parse_packet(data):
    path, pos = osc_read(data); types, pos = osc_read(data, pos); values=[]
    for typ in types[1:]:
        if typ == "i": values.append(struct.unpack(">i", data[pos:pos+4])[0]); pos += 4
        elif typ == "f": values.append(struct.unpack(">f", data[pos:pos+4])[0]); pos += 4
        elif typ == "s": value, pos = osc_read(data, pos); values.append(value)
        else: break
    return path, types, values
def finite(value, label):
    number=float(value)
    if not math.isfinite(number): raise ValueError(f"{label} must be finite")
    return number
def dbamp(db): return max(0.0001, min(2.0, 10.0 ** (finite(db, "gain") / 20.0)))
def as_bool(value): return int(str(value).lower() in ("1", "true", "yes", "on"))
def strict_bool(value, label):
    number=finite(value, label)
    if number not in (0, 1): raise ValueError(f"{label} must be 0 or 1")
    return int(number)
def bounded(value, low, high, label):
    number=finite(value, label)
    if not low <= number <= high: raise ValueError(f"{label} must be {low}..{high}")
    return number
def group_limits(values, name):
    defaults=SPATIAL_LIMITS[name]
    return tuple(float(values.get(f"group.{name}.{key}", defaults[i])) for i,key in enumerate(("x_min","x_max","y_min","y_max","width_min","width_max"))) + defaults[6:]


def _legacy_source_entries(values, channels=16):
    entries = []
    for ch in range(1, channels + 1):
        prefix = f"channel.{ch}."
        entries.append({"id": values[f"{prefix}name"], "name": values[f"{prefix}name"],
                        "mode": "mono", "inputs": [int(values[f"{prefix}input"])],
                        "group": values[f"{prefix}group"]})
    return entries


def _configured_source_entries(values, channels=16):
    """Read the one canonical source map, with a legacy-config fallback."""
    if "source.count" not in values:
        return _legacy_source_entries(values, channels)
    if values.get("source_map_version") != "1":
        raise ValueError("source_map_version must be 1")
    try:
        count = int(values["source.count"])
    except (KeyError, ValueError):
        raise ValueError("source.count must be an integer")
    if count < 1 or count > 16:
        raise ValueError("source.count must be 1..16")
    entries = []
    for index in range(1, count + 1):
        prefix = f"source.{index}."
        required = ("id", "name", "mode", "inputs", "group")
        missing = [field for field in required if f"{prefix}{field}" not in values]
        if missing:
            raise ValueError(f"source {index} missing fields: {missing}")
        raw_inputs = values[f"{prefix}inputs"].split(",")
        try:
            inputs = [int(item.strip()) for item in raw_inputs]
        except ValueError:
            raise ValueError(f"source {index}.inputs must be comma-separated integers")
        entries.append({"id": values[f"{prefix}id"], "name": values[f"{prefix}name"],
                        "mode": values[f"{prefix}mode"], "inputs": inputs,
                        "group": values[f"{prefix}group"]})
    known = {"source_map_version", "source.count"}
    for key in values:
        if key.startswith("source.") and key not in known and not any(key == f"source.{i}.{field}" for i in range(1, count + 1) for field in ("id", "name", "mode", "inputs", "group")):
            raise ValueError(f"unknown source mapping field: {key}")
    return entries


def configured_sources(values, channels=16):
    try:
        return validate_source_map(_configured_source_entries(values, channels), GROUPS, values.get("source_map_version", "1"))
    except SourceMapError as exc:
        raise ValueError(str(exc)) from exc
def validate_parameter(key, numeric, values=None):
    definition, index = control_for_key(key)
    if definition is not None:
        if not definition["writable"]:
            raise ValueError(f"{key} is read-only")
        value_type = definition["value_type"]
        if value_type == "boolean":
            return strict_bool(numeric, key)
        if value_type == "enum":
            number = finite(numeric, key)
            if number not in definition["range"]["values"]:
                raise ValueError(f"{key} has an invalid enumerated value")
            return number
        if definition["range"].get("source", "").startswith("group_limits"):
            name = GROUPS[index]
            limits = group_limits(values or {}, name)
            suffix = "x" if key.endswith("PosX") else "y" if key.endswith("PosY") else "width"
            low, high = {"x": limits[:2], "y": limits[2:4], "width": limits[4:6]}[suffix]
            return bounded(numeric, low, high, key)
        bounds = definition["range"]
        return bounded(numeric, bounds["min"], bounds["max"], key)
    if values is not None and key.startswith("source"):
        import re
        match = re.fullmatch(r"source(\d+)(Trim|Mute|Polarity|HPF|HPFHz|Pan|Balance|Width)", key)
        if match:
            index, suffix = int(match.group(1)), match.group(2)
            sources = values.get("_sources", ())
            if index >= len(sources): raise ValueError(f"invalid source index: {index}")
            mode = sources[index].mode
            if suffix in ("Pan",) and mode != "mono": raise ValueError("pan applies only to mono sources")
            if suffix in ("Balance", "Width") and mode != "stereo": raise ValueError(f"{suffix.lower()} applies only to stereo sources")
            if suffix == "Trim": return bounded(numeric, 0.0001, 4, key)
            if suffix in ("Mute", "HPF"): return strict_bool(numeric, key)
            if suffix == "Polarity":
                number = finite(numeric, key)
                if number not in (-1, 1): raise ValueError(f"{key} must be -1 or 1")
                return number
            if suffix == "HPFHz": return bounded(numeric, 20, 20000, key)
            if suffix == "Pan" or suffix == "Balance": return bounded(numeric, -1, 1, key)
            if suffix == "Width": return bounded(numeric, 0, 1, key)
    if values is not None:
        import re
        match = re.fullmatch(r"input(\d+)(Group|Partner|Mode|Orientation)", key)
        if match:
            index, suffix = int(match.group(1)), match.group(2)
            if not 0 <= index < 16:
                raise ValueError("invalid physical input index")
            if suffix in ("Mode", "Orientation"):
                raise ValueError(f"{key} is read-only; use inputNPartner")
            if suffix == "Group":
                number = finite(numeric, key)
                if number not in range(len(GROUPS)):
                    raise ValueError(f"{key} has an invalid group")
                physical = index + 1
                current = next(source for source in values["_sources"] if physical in source.inputs)
                partner = current.inputs[1] if current.mode == "stereo" and physical == current.inputs[0] else current.inputs[0] if current.mode == "stereo" else 0
                propose_mapping(values, physical, partner=partner, group=GROUPS[int(number)])
                return int(number)
            number = finite(numeric, key)
            if number not in range(17):
                raise ValueError(f"{key} has an invalid stereo partner")
            physical = index + 1
            propose_mapping(values, physical, int(number))
            return int(number)
    if "Neutral" in key: raise ValueError(f"{key} is configuration-only; restart to change it")
    if key.startswith("trim"): return bounded(numeric, 0.0001, 4, key)
    if key.startswith(("mute", "hpf")) or key.endswith(("Mute", "SpatialBypass")): return strict_bool(numeric, key)
    if key.startswith("polarity") or key.endswith("Polarity"):
        number=finite(numeric, key)
        if number not in (-1, 1): raise ValueError(f"{key} must be -1 or 1")
        return number
    if key.startswith("hpfHz"): return bounded(numeric, 20, 20000, key)
    if key.startswith(("groupLevel", "master")): return bounded(numeric, 0, 2, key)
    if key.startswith("group") and "_" in key: raise ValueError(f"{key} is configuration-only; restart to change it")
    if key.endswith(("PosX", "PosY", "Width")):
        suffix_start=key.index("Pos") if "Pos" in key else key.index("Width")
        index=int(key[5:suffix_start])
        limits=group_limits(values or {}, GROUPS[index])
        low,high=(limits[0],limits[1]) if key.endswith("PosX") else (limits[2],limits[3]) if key.endswith("PosY") else (limits[4],limits[5])
        return bounded(numeric, low, high, key)
    if key == "quadSmoothingMs": return bounded(numeric, 0, 1000, key)
    if key.endswith("GainDb"): return bounded(numeric, -120, 24, key)
    if key.endswith("Bus"): return bounded(numeric, 0, 15, key)
    return finite(numeric, key)
def read_config(path):
    values = {}
    with open(path, encoding="utf-8") as stream:
        for line_no, line in enumerate(stream, 1):
            line=line.strip()
            if not line or line.startswith("#"): continue
            if "=" not in line: raise ValueError(f"line {line_no}: expected key=value")
            key, value = line.split("=", 1); values[key.strip()] = value.strip()
    if values.get("version") != "1": raise ValueError("version must be 1")
    channels = int(values.get("channels", "0")); capacity = int(values.get("max_channels", "24"))
    if channels != 16 or channels > capacity or capacity != 24: raise ValueError("mixer must be 16 active / 24 capacity")
    group_count=int(values.get("group.count", str(len(GROUPS))))
    configured_groups=tuple(values.get("group.names", ",".join(GROUPS)).split(","))
    if not 1 <= group_count <= MAX_GROUPS or len(configured_groups) != group_count: raise ValueError("group.count must be 1..8 and match group.names")
    if configured_groups != GROUPS: raise ValueError("production scene must use canonical eight groups")
    sources = configured_sources(values, channels)
    for name in configured_groups:
        finite(values[f"group.{name}.level_db"], f"group.{name}.level_db")
        limits=group_limits(values, name)
        for suffix,expected in zip(("x_min","x_max","y_min","y_max","width_min","width_max"), limits[:6]): bounded(expected, 0, 1, f"group.{name}.{suffix}")
        if limits[0] > limits[1] or limits[2] > limits[3] or limits[4] > limits[5]: raise ValueError(f"{name} spatial constraint min exceeds max")
        for suffix, default, low, high in (("pos_x", limits[6], limits[0], limits[1]), ("pos_y", limits[7], limits[2], limits[3]), ("width", limits[8], limits[4], limits[5]), ("neutral_x", limits[6], limits[0], limits[1]), ("neutral_y", limits[7], limits[2], limits[3]), ("neutral_width", limits[8], limits[4], limits[5]), ("spatial_bypass", 0, 0, 1)):
            key=f"group.{name}.{suffix}"; value=values.get(key, str(default))
            if suffix == "spatial_bypass": strict_bool(value, key)
            else: bounded(value, low, high, key)
    bounded(values.get("quad.smoothing_ms", "30"), 0, 1000, "quad.smoothing_ms")
    finite(values["master.level_db"], "master.level_db")
    channels_out=[]; seen_inputs=set(); seen_outputs=set()
    for ch in range(1, channels + 1):
        prefix=f"channel.{ch}."; row={}
        for field in FIELDS:
            key=prefix+field
            if field in ("name", "input", "output", "group") and key not in values:
                continue
            if key in values: row[field]=values[key]
        source = next((item for item in sources if ch in item.inputs), None)
        if source is None:
            raise ValueError("legacy channel controls must identify one row per logical source")
        if "input" in row and int(row["input"]) != ch:
            raise ValueError(f"legacy channel.{ch}.input disagrees with source map")
        if "output" in row and int(row["output"]) != ch:
            raise ValueError(f"legacy channel.{ch}.output disagrees with source map")
        if "group" in row and row["group"] != source.group:
            raise ValueError(f"legacy channel.{ch}.group disagrees with source map")
        if source.mode != "mono":
            # The legacy channel index is retained only as a compatibility
            # view.  Stereo source controls are represented once by source.
            row["name"] = source.name; row["input"] = str(source.inputs[0]); row["output"] = str(source.inputs[0]); row["group"] = source.group
        else:
            row.setdefault("name", source.name); row.setdefault("input", str(source.inputs[0])); row.setdefault("output", str(source.inputs[0])); row.setdefault("group", source.group)
        if source.mode == "stereo":
            row["name"] = source.name + (" L" if ch == source.inputs[0] else " R")
            row["input"] = str(ch); row["output"] = str(ch); row["group"] = source.group
        inp=int(row["input"]); out=int(row["output"])
        if not 1 <= inp <= 16 or not 1 <= out <= 16: raise ValueError("physical mixer mapping must stay in channels 1..16")
        if inp in seen_inputs or out in seen_outputs: raise ValueError("input/output mapping must be one-to-one")
        if inp != out: raise ValueError("this milestone only permits verified one-to-one input=output mapping")
        seen_inputs.add(inp); seen_outputs.add(out)
        if row["group"] not in GROUPS: raise ValueError(f"invalid group for channel {ch}")
        trim=finite(row["trim_db"], f"channel.{ch}.trim_db"); hpf_hz=finite(row["hpf_hz"], f"channel.{ch}.hpf_hz")
        if not -60 <= trim <= 12: raise ValueError("trim must be -60..12 dB")
        if not 20 <= hpf_hz <= 20000: raise ValueError("HPF frequency must be 20..20000 Hz")
        as_bool(row["mute"]); as_bool(row["hpf"])
        if int(row["polarity"]) not in (-1, 1): raise ValueError("polarity must be -1 or 1")
        channels_out.append(row)
    if seen_inputs != set(range(1,17)) or seen_outputs != set(range(1,17)): raise ValueError("mapping must cover all 16 channels")
    values["_sources"] = sources
    return values, channels_out
def _contract_default(definition, index, values, channels):
    template = definition["key_template"]
    if definition["scope"] == "channel":
        row = channels[index]
        if template == "channelNGroup": return row["group"]
        field = definition["default_source"].split(".")[-1]
        value = row[field]
        if template == "trimN": return dbamp(value)
        if definition["value_type"] == "boolean": return as_bool(value)
        if template == "polarityN": return int(value)
        return float(value)
    if definition["scope"] == "group":
        name = GROUPS[index]
        suffix = definition["default_source"].replace("group.<name>.", "")
        value = values.get(f"group.{name}.{suffix}")
        if template == "groupLevelN": return dbamp(value)
        if definition["value_type"] == "boolean": return as_bool(value)
        return float(value)
    if definition["scope"] == "master": return dbamp(values["master.level_db"])
    return CONTRACT_VERSION


def controls(values, channels):
    result=[]
    for i,row in enumerate(channels):
        for definition in control_definitions():
            if definition["scope"] != "channel": continue
            result.append((definition["key_template"].replace("N", str(i)), _contract_default(definition, i, values, channels)))
        group=GROUPS.index(row["group"])
        result += [(f"group{i}_{g}", int(g == group)) for g in range(MAX_GROUPS)]
    group_definitions = [item for item in control_definitions() if item["scope"] == "group"]
    for g in range(len(GROUPS)):
        for definition in group_definitions:
            result.append((definition["key_template"].replace("N", str(g)), _contract_default(definition, g, values, channels)))
    for definition in control_definitions():
        if definition["scope"] == "master":
            result.append((definition["key_template"], _contract_default(definition, 0, values, channels)))
        elif definition["scope"] == "status":
            result.append((definition["key_template"], _contract_default(definition, 0, values, channels)))
    for g,name in enumerate(GROUPS):
        limits=group_limits(values, name)
        result += [(f"group{g}NeutralX", float(values.get(f"group.{name}.neutral_x", limits[6]))), (f"group{g}NeutralY", float(values.get(f"group.{name}.neutral_y", limits[7]))), (f"group{g}NeutralWidth", float(values.get(f"group.{name}.neutral_width", limits[8])))]
    result.append(("quadSmoothingMs", float(values.get("quad.smoothing_ms", 30))))
    result.extend(source_controls(values, channels))
    result.append(("sourceMapVersion", str(values.get("source_map_version", "1"))))
    for index, source in enumerate(values["_sources"]):
        result.extend([(f"source{index}Id", source.id), (f"source{index}Name", source.name),
                       (f"source{index}Mode", source.mode), (f"source{index}Inputs", ",".join(map(str, source.inputs))),
                       (f"source{index}Group", source.group), (f"source{index}MeterL", f"input.{source.inputs[0]}.left"),
                       (f"source{index}MeterR", f"input.{source.inputs[-1]}.right")])
    result.extend(mapping_state(values))
    return result


def _source_channel(sources, channels, source):
    return channels[next(i for i, row in enumerate(channels) if int(row["input"]) == source.inputs[0])]


def source_controls(values, channels):
    sources = values["_sources"]
    result = []
    for index, source in enumerate(sources):
        row = _source_channel(sources, channels, source)
        defaults = {
            "Trim": dbamp(row["trim_db"]), "Mute": as_bool(row["mute"]),
            "Polarity": int(row["polarity"]), "HPF": as_bool(row["hpf"]),
            "HPFHz": float(row["hpf_hz"]), "Pan": 0.0, "Balance": 0.0, "Width": 1.0,
        }
        for definition in source_controls_for_mode(source.mode):
            suffix = definition["key_template"].replace("sourceN", "").replace("N", "")
            result.append((f"source{index}{suffix}", defaults[suffix]))
    return result


def source_contract_for(values):
    return source_contract(values["_sources"])


def source_map_snapshot(values):
    return {"source_map_version": values.get("source_map_version", "1"),
            "sources": [source.snapshot() for source in values["_sources"]]}


def mapping_state(values):
    """Return normalized, per-physical-input mapping state for clients."""
    result = []
    for physical in range(1, 17):
        source = next(source for source in values["_sources"] if physical in source.inputs)
        stereo = source.mode == "stereo"
        result.extend([
            (f"input{physical - 1}Group", GROUPS.index(source.group)),
            (f"input{physical - 1}Partner", (source.inputs[1] if stereo and physical == source.inputs[0]
                                               else source.inputs[0] if stereo else 0)),
            (f"input{physical - 1}Mode", 1 if stereo else 0),
            (f"input{physical - 1}Orientation", 1 if stereo and physical == source.inputs[0]
                                                  else 2 if stereo else 0),
        ])
    return result


def _runtime_source_entries(values, physical, partner=0, group=None):
    """Build a complete proposed map for one atomic mapping edit."""
    if not 1 <= physical <= 16:
        raise ValueError("physical input must be 1..16")
    if partner == physical:
        raise ValueError("an input cannot be its own stereo partner")
    if not 0 <= partner <= 16:
        raise ValueError("stereo partner must be 0..16")
    current = {number: source for source in values["_sources"] for number in source.inputs}
    if partner and current[partner].mode == "stereo" and physical not in current[partner].inputs:
        raise ValueError("stereo partner is already paired")
    affected = {physical} | ({partner} if partner else set())
    entries = []
    for source in values["_sources"]:
        remaining = [number for number in source.inputs if number not in affected]
        for number in remaining:
            split_id = f"{source.id}_{number}" if source.mode == "stereo" else current[number].id
            split_name = f"{source.name} {'L' if number == source.inputs[0] else 'R'}" if source.mode == "stereo" else current[number].name
            entries.append({"id": split_id, "name": split_name,
                            "mode": "mono", "inputs": [number], "group": current[number].group})
    if partner:
        left, right = current[physical], current[partner]
        selected_group = group if group is not None else left.group
        entries.append({"id": left.id, "name": f"{left.name} / {right.name}",
                        "mode": "stereo", "inputs": [physical, partner], "group": selected_group})
    else:
        source = current[physical]
        selected_group = group if group is not None else source.group
        entries.append({"id": source.id, "name": source.name, "mode": "mono",
                        "inputs": [physical], "group": selected_group})
    return sorted(entries, key=lambda entry: entry["inputs"][0])


def propose_mapping(values, physical, partner=None, group=None):
    """Validate and return a complete replacement map without mutating values."""
    current = next(source for source in values["_sources"] if physical in source.inputs)
    if partner is None:
        partner = current.inputs[1] if current.mode == "stereo" and physical == current.inputs[0] else current.inputs[0] if current.mode == "stereo" else 0
    entries = _runtime_source_entries(values, physical, partner, group)
    return validate_source_map(entries, GROUPS, values.get("source_map_version", "1"))


def active_source_nodes(values):
    return tuple(ROUTER_NODE + index for index in range(len(values["_sources"])))


def smoothing_targets(values):
    """All live nodes whose controls use the shared smoothing time."""
    return active_source_nodes(values) + tuple(GROUP_NODE_BASE + g for g in range(8)) + (MASTER_NODE,)


def legacy_source_for_key(key, values):
    """Return the logical source for a legacy physical-channel control."""
    import re
    match = re.fullmatch(r"(?:hpfHz|trim|mute|polarity|hpf)(\d+)", key)
    if not match:
        return None
    physical = int(match.group(1)) + 1
    return next((source for source in values.get("_sources", ()) if physical in source.inputs), None)


def legacy_stereo_write_error(key, values):
    source = legacy_source_for_key(key, values)
    if source is not None and source.mode == "stereo":
        return "legacy channel control is ambiguous for stereo source; use source-level controls"
    return None


def apply_smoothing(sock, sc_port, values, seconds):
    for target in smoothing_targets(values):
        send(sock, sc_port, packet("/n_set", ",isf", [target, "smoothing", seconds]))


def dsp_controls(values, channels):
    result=[]
    for name,value in controls(values, channels):
        if name == "quadSmoothingMs": result.append(("quadSmoothing", float(value) / 1000.0)); continue
        if "Neutral" in name: continue
        if name.startswith("group") and "_" in name: continue
        if name.endswith("GainDb"): result.append((name[:-5], dbamp(value)))
        else: result.append((name, value))
    for i,row in enumerate(channels): result.append((f"groupSelect{i}", GROUPS.index(row["group"])))
    return result


def source_router_controls(values, channels):
    """Translate the canonical map to bounded controls for reusable router slots."""
    state = dict(source_controls(values, channels))
    result = []
    for index, source in enumerate(values["_sources"]):
        result.extend([(f"sourceMode{index}", 0 if source.mode == "mono" else 1),
                       (f"sourceInputL{index}", source.inputs[0] - 1),
                       (f"sourceInputR{index}", (source.inputs[-1] if source.mode == "stereo" else source.inputs[0]) - 1),
                       (f"sourceGroup{index}", GROUPS.index(source.group)),
                       (f"sourceTrim{index}", state[f"source{index}Trim"]),
                       (f"sourceMute{index}", state[f"source{index}Mute"]),
                       (f"sourcePolarityL{index}", state[f"source{index}Polarity"]),
                       (f"sourcePolarityR{index}", state[f"source{index}Polarity"]),
                       (f"sourceHPF{index}", state[f"source{index}HPF"]),
                       (f"sourceHPFHz{index}", state[f"source{index}HPFHz"]),
                       (f"sourcePan{index}", state.get(f"source{index}Pan", 0.0)),
                       (f"sourceBalance{index}", state.get(f"source{index}Balance", 0.0)),
                       (f"sourceWidth{index}", state.get(f"source{index}Width", 1.0))])
    return result


def source_node_controls(values, channels, index):
    source = values["_sources"][index]
    state = dict(source_controls(values, channels))
    return [("sourceMode", 0 if source.mode == "mono" else 1),
            ("sourceInputL", source.inputs[0] - 1),
            ("sourceInputR", (source.inputs[-1] if source.mode == "stereo" else source.inputs[0]) - 1),
            ("sourceGroup", GROUPS.index(source.group)),
            ("sourceTrim", state[f"source{index}Trim"]),
            ("sourceMute", state[f"source{index}Mute"]),
            ("sourcePolarityL", state[f"source{index}Polarity"]),
            ("sourcePolarityR", state[f"source{index}Polarity"]),
            ("sourceHPF", state[f"source{index}HPF"]),
            ("sourceHPFHz", state[f"source{index}HPFHz"]),
            ("sourcePan", state.get(f"source{index}Pan", 0.0)),
            ("sourceBalance", state.get(f"source{index}Balance", 0.0)),
            ("sourceWidth", state.get(f"source{index}Width", 1.0)),
            ("smoothing", float(values.get("quad.smoothing_ms", 30)) / 1000.0)]


def apply_runtime_mapping(sock, sc_port, values, channels, state, proposed):
    """Commit a validated map and refresh all dependent state atomically."""
    old_sources = values["_sources"]
    old_by_id = {source.id: index for index, source in enumerate(old_sources)}
    old_state = dict(state)
    values["_sources"] = tuple(proposed)
    refreshed = dict(controls(values, channels))
    for index, source in enumerate(values["_sources"]):
        old_index = old_by_id.get(source.id)
        if old_index is None:
            continue
        for suffix in ("Trim", "Mute", "Polarity", "HPF", "HPFHz", "Pan", "Balance", "Width"):
            old_key = f"source{old_index}{suffix}"
            new_key = f"source{index}{suffix}"
            if old_key in old_state and new_key in refreshed:
                refreshed[new_key] = old_state[old_key]
    # Rebuild the reusable source slots from the proposed complete map.  No
    # state is published until validation and the full replacement are ready.
    for node in range(ROUTER_NODE, ROUTER_NODE + 16):
        send(sock, sc_port, packet("/n_free", ",i", [node]))
    for index in range(len(values["_sources"])):
        send_snew(sock, sc_port, "sc_adat_router", ROUTER_NODE + index, NODE_ROUTING,
                  source_node_controls(values, channels, index), action=1)
    state.clear()
    state.update(refreshed)
def send(sock, port, data): sock.sendto(data, ("127.0.0.1", port))
def send_to(sock, address, data): sock.sendto(data, address)

def reply_destination(source, reply_port):
    """Return a per-request destination, preserving the sender IP."""
    if reply_port is None:
        return source
    if not isinstance(reply_port, (int, float)):
        raise ValueError("reply port must be an integer 1..65535")
    try:
        number = float(reply_port)
    except (TypeError, ValueError, OverflowError):
        raise ValueError("reply port must be an integer 1..65535")
    if not math.isfinite(number) or not number.is_integer() or not 1 <= number <= 65535:
        raise ValueError("reply port must be an integer 1..65535")
    return source[0], int(number)

def request_destination(source, values, expected_without_port, expected_with_port):
    """Validate an optional final reply port and return (destination, error)."""
    if len(values) == expected_without_port:
        return source, None
    if len(values) == expected_with_port:
        try:
            return reply_destination(source, values[-1]), None
        except ValueError as exc:
            return source, str(exc)
    return source, None


def state_chunk_packets(state, snapshot, entries_per_chunk=BULK_STATE_ENTRIES):
    """Build bounded bulk-state datagrams; values may be numeric or strings."""
    items = sorted(state.items())
    total = max(1, (len(items) + entries_per_chunk - 1) // entries_per_chunk)
    chunks = []
    for index in range(total):
        pairs = items[index * entries_per_chunk:(index + 1) * entries_per_chunk]
        types = ",sii"
        values = [str(snapshot), index, total]
        for key, value in pairs:
            types += "s" + ("s" if isinstance(value, str) else "f")
            values.extend([key, value])
        chunks.append(packet("/mixer/state-chunk", types, values))
    completion = packet("/mixer/state-complete", ",sii", [str(snapshot), total, len(items)])
    legacy_completion = packet("/mixer/get-all-done", ",i", [len(items)])
    return chunks, completion, legacy_completion
def db(value): return -120.0 if value <= 1e-9 else 20.0 * math.log10(min(1.0, max(1e-9, value)))
ROUTER_NODE=3900; GROUP_NODE_BASE=4000; MASTER_NODE=4100
NODE_ROUTING=1000; NODE_SPATIAL=1001; NODE_MASTER=1002
def send_snew(sock, port, name, node, target, controls_list, action=0):
    vals=[name, node, action, target]; types=",siii"
    for name,value in controls_list:
        if isinstance(value, str): continue
        if name in ("inbus", "outbus", "groupbus", "out0", "out1", "out2", "out3"):
            # scsynth controls are numeric OSC values; retain bus identity as
            # an exact integer-valued float so the SynthDef's bus UGen sees
            # the same value as its default/control representation.
            types += "sf"; vals += [name, float(value)]
        else:
            types += "sf"; vals += [name, value]
    send(sock, port, packet("/s_new", types, vals))
def start_graph(sock, port, values, channels):
    sock.settimeout(0.25)
    send(sock, port, packet("/sync", ",i", [1]))
    deadline=time.time()+2.0
    while time.time() < deadline:
        try:
            if parse_packet(sock.recv(65535))[0] == "/synced": break
        except (socket.timeout, ValueError, IndexError): pass
    else: raise RuntimeError("scsynth synchronization failed before graph creation")
    for _ in range(20):
        send(sock, port, packet("/notify", ",i", [1]));
        for node in tuple(ROUTER_NODE + i for i in range(16)) + (MASTER_NODE, NODE_ROUTING, NODE_SPATIAL, NODE_MASTER):
            send(sock, port, packet("/n_free", ",i", [node]))
        # Build an explicit feed-forward chain.  /g_new action 0 inserts at
        # the head, while action 3 inserts after the target.  The latter is
        # essential here: relying on packet order or repeated add-to-head
        # reverses the execution order seen by In.ar.
        send(sock, port, packet("/g_new", ",iii", [NODE_ROUTING, 0, 0]))
        send(sock, port, packet("/g_new", ",iii", [NODE_SPATIAL, 3, NODE_ROUTING]))
        send(sock, port, packet("/g_new", ",iii", [NODE_MASTER, 3, NODE_SPATIAL]))
        for index in range(len(values["_sources"])):
            send_snew(sock, port, "sc_adat_router", ROUTER_NODE + index, NODE_ROUTING, source_node_controls(values, channels, index), action=1)
        # Add siblings at the tail so the queried tree is 4000..4007.  Their
        # order is not relied on for signal flow, but it is part of the
        # deterministic ownership contract and makes diagnostics unambiguous.
        for g in range(8): send_snew(sock, port, "sc_adat_group", GROUP_NODE_BASE + g, NODE_SPATIAL, group_controls(values, g), action=1)
        master_name = "sc_adat_quad_master" if values.get("_mode", "stereo") == "quad" else "sc_adat_stereo_master"
        master_node = MASTER_NODE
        send_snew(sock, port, master_name, master_node, NODE_MASTER, master_controls(values))
        send(sock, port, packet("/sync", ",i", [2])); synced=False; deadline=time.time()+2.0
        while time.time() < deadline and not synced:
            try: path, fail_types, fail_values = parse_packet(sock.recv(65535))
            except (socket.timeout, ValueError, IndexError): break
            if path == "/synced": synced=True
            if path == "/fail":
                if fail_values and fail_values[0] == "/n_free":
                    continue
                raise RuntimeError(f"scsynth rejected mixer graph: {fail_values}")
        if synced:
            # Reassert bus controls after node creation.  This is deliberately
            # synchronized: it distinguishes a control-assignment problem
            # from an execution-order problem in the integration test.
            for g in range(8):
                send(sock, port, packet("/n_set", ",isf", [GROUP_NODE_BASE + g, "outbus", float(BUS_QUAD_GROUPS + g * 4)]))
            send(sock, port, packet("/sync", ",i", [3])); deadline=time.time()+2.0
            while time.time() < deadline:
                try:
                    if parse_packet(sock.recv(65535))[0] == "/synced": break
                except (socket.timeout, ValueError, IndexError): pass
            else: raise RuntimeError("scsynth synchronization failed after bus assignment")
            sock.settimeout(None); return
        time.sleep(0.1)
    sock.settimeout(None)
    raise RuntimeError("scsynth did not acknowledge mixer node")
def router_controls(values, channels):
    return source_node_controls(values, channels, 0)
def group_controls(values, g):
    name=GROUPS[g]; limits=group_limits(values, name)
    y = 1.0 if values.get("_mode", "stereo") == "stereo" else float(values.get(f"group.{name}.pos_y", limits[7])) * 2 - 1
    return [("groupIndex",g),("inbus",BUS_GROUP_STEMS+g*2),("outbus",BUS_QUAD_GROUPS+g*4),("gain",dbamp(values[f"group.{name}.level_db"])),("mute",0),("x",float(values.get(f"group.{name}.pos_x",limits[6]))*2-1),("y",y),("width",float(values.get(f"group.{name}.width",limits[8]))),("spatialBypass",int(values.get(f"group.{name}.spatial_bypass",0))), ("xMin",limits[0]*2-1),("xMax",limits[1]*2-1),("yMin",limits[2]*2-1),("yMax",limits[3]*2-1),("widthMin",limits[4]),("widthMax",limits[5]),("neutralX",limits[6]*2-1),("neutralY",limits[7]*2-1),("neutralWidth",limits[8]),("smoothing",float(values.get("quad.smoothing_ms",30))/1000.0)]
def master_controls(values):
    result=[("master",dbamp(values["master.level_db"])),("smoothing",float(values.get("quad.smoothing_ms",30))/1000.0)]
    return result
def node_update(key, value, mode="stereo", values=None):
    if key.startswith("source"):
        import re
        match = re.fullmatch(r"source(\d+)(Trim|Mute|Polarity|HPF|HPFHz|Pan|Balance|Width)", key)
        if match:
            index, suffix = match.groups()
            dsp_suffix = {"Trim": "Trim", "Mute": "Mute", "Polarity": "PolarityL", "HPF": "HPF", "HPFHz": "HPFHz", "Pan": "Pan", "Balance": "Balance", "Width": "Width"}[suffix]
            return ROUTER_NODE + int(index), f"source{dsp_suffix}", value
    import re
    legacy = re.fullmatch(r"(hpfHz|trim|mute|polarity|hpf)(\d+)", key)
    if legacy and values is not None:
        field, physical_index = legacy.groups()
        physical = int(physical_index) + 1
        for index, source in enumerate(values.get("_sources", ())):
            if physical in source.inputs:
                suffix = {"trim": "Trim", "mute": "Mute", "polarity": "PolarityL", "hpfHz": "HPFHz", "hpf": "HPF"}[field]
                return ROUTER_NODE + index, f"source{suffix}", value
    if key.startswith("group") and key[5:6].isdigit():
        g=int(key[5:key.index("Pos") if "Pos" in key else key.index("Width") if "Width" in key else key.index("Spatial")])
        node=GROUP_NODE_BASE+g
        suffix="x" if key.endswith("PosX") else "y" if key.endswith("PosY") else "width" if key.endswith("Width") else "spatialBypass" if key.endswith("SpatialBypass") else "gain" if key.startswith("groupLevel") else None
        if suffix == "y" and mode == "stereo": return None
        if suffix: return node,suffix,(value*2-1 if suffix in ("x","y") else value)
    if key.startswith("groupLevel"):
        return GROUP_NODE_BASE+int(key[len("groupLevel"):]),"gain",value
    if key == "master":
        return MASTER_NODE,key,value
    return ROUTER_NODE,key,value
def apply(config, port=57110, mode=None):
    values, channels=read_config(config)
    if mode is not None:
        if mode not in ("stereo", "quad"): raise ValueError("mode must be stereo or quad")
        values["_mode"]=mode
    sock=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); start_graph(sock, port, values, channels); time.sleep(.15); return values, channels
def serve(config, listen=57120, sc_port=57110, start=True, mode=None):
    values, channels=read_config(config)
    if mode is not None:
        if mode not in ("stereo", "quad"): raise ValueError("mode must be stereo or quad")
        values["_mode"]=mode
    sock=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.bind(("0.0.0.0", listen)); initial=controls(values, channels); state=dict(initial); meter_values=[0.0] * METER_WIDTH; snapshot_id=0
    if start: start_graph(sock, sc_port, values, channels)
    def shutdown(_signum, _frame):
        try:
            send(sock, sc_port, packet("/n_set", ",isf", [MASTER_NODE, "master", 0.0])); time.sleep(0.06)
            for node in tuple(ROUTER_NODE + i for i in range(16)) + (NODE_ROUTING, NODE_SPATIAL, NODE_MASTER): send(sock, sc_port, packet("/n_free", ",i", [node]))
        finally:
            raise SystemExit(0)
    signal.signal(signal.SIGTERM, shutdown); signal.signal(signal.SIGINT, shutdown)
    meters=0
    while True:
        data, address=sock.recvfrom(65535); path, types, vals=parse_packet(data)
        if path == "/mixer/meter":
            numeric=[float(x) for x in vals if isinstance(x, (int, float)) and math.isfinite(float(x))]
            if len(numeric) >= METER_WIDTH: meter_values=numeric[-METER_WIDTH:]
            meters += 1
        elif path == "/mixer/meters":
            destination, port_error=request_destination(address, vals, 0, 1)
            if port_error is not None:
                send_to(sock, address, packet("/mixer/error", ",s", [port_error])); continue
            if len(vals) not in (0, 1) or (len(vals) == 1 and types not in (",i", ",f")):
                send_to(sock, address, packet("/mixer/error", ",s", ["expected /mixer/meters [,i|f reply_port]"])); continue
            send_to(sock, destination, packet("/mixer/meters", "," + "f" * METER_WIDTH, meter_values))
        elif path == "/mixer/set" and types in (",sf", ",sfi", ",sff") and len(vals) in (2, 3):
            destination, port_error=request_destination(address, vals, 2, 3)
            if port_error is not None:
                send_to(sock, address, packet("/mixer/error", ",s", [port_error])); continue
            key, value=vals[:2]; allowed={name for name,_ in controls(values, channels)}
            if key not in allowed:
                send_to(sock, destination, packet("/mixer/error", ",s", ["invalid parameter"])); continue
            legacy_error = legacy_stereo_write_error(key, values)
            if legacy_error is not None:
                send_to(sock, destination, packet("/mixer/error", ",s", [legacy_error]))
                continue
            try: numeric=float(value)
            except (TypeError, ValueError): send_to(sock, destination, packet("/mixer/error", ",s", ["value is not numeric"])); continue
            if not math.isfinite(numeric): send_to(sock, destination, packet("/mixer/error", ",s", ["value must be finite"])); continue
            try: numeric=validate_parameter(key, numeric, values)
            except ValueError as exc:
                send_to(sock, destination, packet("/mixer/error", ",s", [str(exc)])); continue
            import re
            mapping_match = re.fullmatch(r"input(\d+)(Group|Partner)", key)
            if mapping_match:
                physical = int(mapping_match.group(1)) + 1
                try:
                    if mapping_match.group(2) == "Partner":
                        proposed = propose_mapping(values, physical, int(numeric))
                    else:
                        proposed = propose_mapping(values, physical, group=GROUPS[int(numeric)])
                    apply_runtime_mapping(sock, sc_port, values, channels, state, proposed)
                except (ValueError, SourceMapError) as exc:
                    send_to(sock, destination, packet("/mixer/error", ",s", [str(exc)])); continue
                for normalized_key, normalized_value in mapping_state(values):
                    send_to(sock, destination, packet("/mixer/state", ",sf", [normalized_key, normalized_value]))
                send_to(sock, destination, packet("/mixer/ok", ",s", [key]))
                continue
            state[key]=numeric
            if key == "quadSmoothingMs":
                apply_smoothing(sock, sc_port, values, numeric / 1000.0)
            else:
                update=node_update(key, numeric, values.get("_mode", "stereo"), values)
                if update is not None:
                    target,dsp_key,dsp_value=update
                    send(sock, sc_port, packet("/n_set", ",isf", [target, dsp_key, dsp_value]))
                    if key.startswith("source") and key.endswith("Polarity"):
                        index = int(key[len("source"):key.index("Polarity")])
                        send(sock, sc_port, packet("/n_set", ",isf", [ROUTER_NODE + index, "sourcePolarityR", dsp_value]))
            send_to(sock, destination, packet("/mixer/ok", ",s", [key]))
        elif path == "/mixer/set":
            send_to(sock, address, packet("/mixer/error", ",s", ["expected /mixer/set ,sf key value [reply_port]"]))
        elif path == "/mixer/get" and types in (",s", ",si", ",sf") and len(vals) in (1, 2):
            destination, port_error=request_destination(address, vals, 1, 2)
            if port_error is not None:
                send_to(sock, address, packet("/mixer/error", ",s", [port_error])); continue
            key=str(vals[0]) if vals else "master"
            if key not in state: send_to(sock, destination, packet("/mixer/error", ",s", ["invalid parameter"]))
            else:
                value=state[key]
                send_to(sock, destination, packet("/mixer/state", ",ss", [key, value]) if isinstance(value, str) else packet("/mixer/state", ",sf", [key, value]))
        elif path == "/mixer/get":
            send_to(sock, address, packet("/mixer/error", ",s", ["expected /mixer/get ,s key [reply_port]"]))
        elif path == "/mixer/get-all" and types == ",":
            snapshot_id += 1
            chunks, completion, legacy_completion = state_chunk_packets(state, snapshot_id)
            for chunk in chunks: send_to(sock, address, chunk)
            # Preserve the pre-chunk compatibility stream for established
            # listeners; source metadata is deliberately represented by small
            # individual keys so every packet stays bounded.
            for key, value in sorted(state.items()):
                send_to(sock, address, packet("/mixer/state", ",ss", [key, value]) if isinstance(value, str) else packet("/mixer/state", ",sf", [key, value]))
            send_to(sock, address, completion)
            send_to(sock, address, legacy_completion)
def get_meters(port=57120):
    sock=socket.socket(socket.AF_INET, socket.SOCK_DGRAM); sock.settimeout(2); send(sock, port, packet("/mixer/meters", ","))
    path, _, values=parse_packet(sock.recv(65535))
    if path != "/mixer/meters" or len(values) != METER_WIDTH: raise RuntimeError("meter stream unavailable")
    return [float(x) for x in values]
def print_meters(port=57120):
    values=get_meters(port)
    print("inputs  peak/rms dBFS")
    for i in range(16): print(f"I{i+1:02d} {db(values[i]):7.1f}/{db(values[16+i]):7.1f}", end="  " if i % 2 == 0 else "\n")
    print("groups  peak/rms dBFS")
    for i,name in enumerate(GROUPS): print(f"{name:<11} {db(values[32+i]):7.1f}/{db(values[40+i]):7.1f}")
    print("outputs peak/rms dBFS")
    for i in range(16): print(f"O{i+1:02d} {db(values[48+i]):7.1f}/{db(values[64+i]):7.1f}", end="  " if i % 2 == 0 else "\n")
def print_probe(port=57120, duration=5):
    duration=max(1, min(30, int(duration))); maximum=[0.0] * 16; deadline=time.time() + duration
    while time.time() < deadline:
        values=get_meters(port)
        for i in range(16): maximum[i]=max(maximum[i], values[i])
        time.sleep(0.5)
    print(f"input probe: {duration}s, signal threshold -80.0 dBFS")
    for i,value in enumerate(maximum): print(f"I{i+1:02d} {'SIGNAL' if db(value) > -80 else 'silence':7s} peak={db(value):7.1f} dBFS")
def tone(output, duration=5, port=57110):
    if not 0 <= output <= 15: raise ValueError("tone output bus must be 0..15")
    sock=socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    node=3100
    # sc_adat_scan is deliberately used directly on a hardware-output bus;
    # it never reads an input or enters the mixer node.
    types=",siiisisfsfsi"
    values=["sc_adat_scan", node, 0, 0, "output", output, "freq", 440.0, "level", -30.0, "gate", 1]
    send(sock, port, packet("/s_new", types, values))
    try:
        time.sleep(max(1, min(5, int(duration))) - 0.5)
    finally:
        send(sock, port, packet("/n_set", ",isi", [node, "gate", 0]))
        time.sleep(0.5)
def main():
    parser=argparse.ArgumentParser(); parser.add_argument("action", choices=("validate", "apply", "serve", "meters", "probe", "tone")); parser.add_argument("config", nargs="?"); parser.add_argument("--port", type=int, default=57110); parser.add_argument("--listen", type=int, default=57120); parser.add_argument("--duration", type=int, default=5); parser.add_argument("--output", type=int); parser.add_argument("--mode", choices=("stereo", "quad")); parser.add_argument("--no-node", action="store_true")
    args=parser.parse_args()
    try:
        if args.action == "validate": values, channels=read_config(args.config); print(f"valid mixer config: {len(channels)} channels, inputs/outputs 1..16, capacity 24")
        elif args.action == "apply": apply(args.config, args.port, args.mode); print(f"mixer graph applied: router, 8 groups, {args.mode or 'stereo'} master")
        elif args.action == "meters": print_meters(args.listen)
        elif args.action == "probe": print_probe(args.listen, args.duration)
        elif args.action == "tone": tone(args.output, args.duration, args.port)
        else: serve(args.config, args.listen, args.port, not args.no_node, args.mode)
    except (OSError, ValueError, OverflowError) as exc: print(f"mixerctl: {exc}", file=sys.stderr); return 1
    return 0
if __name__ == "__main__": sys.exit(main())
