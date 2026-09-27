"""Authoritative logical-source mapping and immutable snapshots.

The source map is deliberately independent of OSC and DSP.  It is the one
validated description consumed by configuration, the mixer graph, control
surfaces, meters, and future recording manifests.
"""
from dataclasses import dataclass
from typing import Iterable, Mapping
import math

PHYSICAL_INPUTS = frozenset(range(1, 17))
SOURCE_MODES = frozenset(("mono", "stereo"))


class SourceMapError(ValueError):
    """A proposed source map is not safe to apply."""


@dataclass(frozen=True)
class Source:
    id: str
    name: str
    mode: str
    inputs: tuple[int, ...]
    group: str

    def snapshot(self):
        return {
            "id": self.id,
            "name": self.name,
            "mode": self.mode,
            "inputs": list(self.inputs),
            "group": self.group,
        }


def _text(value, field):
    if not isinstance(value, str) or not value.strip():
        raise SourceMapError(f"{field} must be a non-empty string")
    return value.strip()


def validate_source_map(entries: Iterable[Mapping], groups: Iterable[str], version="1"):
    """Return an immutable, validated tuple of :class:`Source` objects."""
    if version != "1":
        raise SourceMapError("source_map_version must be 1")
    valid_groups = frozenset(groups)
    if not valid_groups:
        raise SourceMapError("source map requires at least one destination group")
    if not isinstance(entries, (list, tuple)):
        raise SourceMapError("sources must be a list")
    result = []
    ids = set()
    used = []
    for position, raw in enumerate(entries, 1):
        if not isinstance(raw, Mapping):
            raise SourceMapError(f"source {position} must be an object")
        required = {"id", "name", "mode", "inputs", "group"}
        unknown = set(raw) - required
        missing = required - set(raw)
        if unknown:
            raise SourceMapError(f"source {position} has unknown fields: {sorted(unknown)}")
        if missing:
            raise SourceMapError(f"source {position} missing fields: {sorted(missing)}")
        source_id = _text(raw["id"], f"source {position}.id")
        name = _text(raw["name"], f"source {position}.name")
        mode = _text(raw["mode"], f"source {position}.mode")
        if mode not in SOURCE_MODES:
            raise SourceMapError(f"source {source_id}: unknown mode {mode!r}")
        if source_id in ids:
            raise SourceMapError(f"duplicate source ID: {source_id}")
        ids.add(source_id)
        if not isinstance(raw["inputs"], (list, tuple)):
            raise SourceMapError(f"source {source_id}.inputs must be a list")
        inputs = tuple(raw["inputs"])
        expected = 1 if mode == "mono" else 2
        if len(inputs) != expected:
            raise SourceMapError(f"source {source_id}: {mode} requires exactly {expected} inputs")
        if any(type(value) is not int for value in inputs):
            raise SourceMapError(f"source {source_id}.inputs must contain integers")
        if any(value not in PHYSICAL_INPUTS for value in inputs):
            raise SourceMapError(f"source {source_id}: inputs must be in 1..16")
        if len(set(inputs)) != len(inputs):
            raise SourceMapError(f"source {source_id}: inputs must be unique and ordered")
        group = _text(raw["group"], f"source {source_id}.group")
        if group not in valid_groups:
            raise SourceMapError(f"source {source_id}: nonexistent group {group!r}")
        used.extend(inputs)
        result.append(Source(source_id, name, mode, inputs, group))
    if set(used) != PHYSICAL_INPUTS or len(used) != len(PHYSICAL_INPUTS):
        missing = sorted(PHYSICAL_INPUTS - set(used))
        duplicate = sorted(value for value in set(used) if used.count(value) > 1)
        details = []
        if missing:
            details.append(f"missing inputs {missing}")
        if duplicate:
            details.append(f"duplicate inputs {duplicate}")
        raise SourceMapError("source map must cover inputs 1..16 exactly once (" + ", ".join(details) + ")")
    return tuple(result)


def source_map_snapshot(sources, version="1"):
    """Small JSON-safe metadata payload for future consumers."""
    entries = [source.snapshot() if isinstance(source, Source) else source for source in sources]
    checked = validate_source_map(entries, {entry["group"] for entry in entries}, version)
    return {
        "source_map_version": version,
        "sources": [source.snapshot() for source in checked],
    }


class AtomicSourceMap:
    """Hold a working map and replace it only after whole-map validation."""

    def __init__(self, entries, groups, version="1"):
        self._groups = tuple(groups)
        self._version = version
        self._sources = validate_source_map(entries, self._groups, version)

    @property
    def sources(self):
        return self._sources

    def replace(self, entries):
        proposed = validate_source_map(entries, self._groups, self._version)
        self._sources = proposed
        return proposed

    def snapshot(self):
        return {"source_map_version": self._version,
                "sources": [source.snapshot() for source in self._sources]}


def mono_pan_gains(pan):
    """Equal-power left/right gains for the mono source pan control."""
    if not -1 <= pan <= 1:
        raise SourceMapError("mono pan must be -1..1")
    left = math.cos((pan + 1) * math.pi * 0.25)
    right = math.sin((pan + 1) * math.pi * 0.25)
    return (0.0 if abs(left) < 1e-12 else left, 0.0 if abs(right) < 1e-12 else right)


def stereo_balance_width(left, right, balance=0.0, width=1.0):
    """Return oriented stereo samples after linked balance/width processing."""
    if not -1 <= balance <= 1 or not 0 <= width <= 1:
        raise SourceMapError("stereo balance must be -1..1 and width 0..1")
    mid = (left + right) * 0.5
    side = (left - right) * 0.5 * width
    left_gain = math.sqrt((1 - balance) * 0.5) * math.sqrt(2)
    right_gain = math.sqrt((1 + balance) * 0.5) * math.sqrt(2)
    return (mid + side) * left_gain, (mid - side) * right_gain
