#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
ROM="$ROOT/dyaxis/firmware/original/41.005.415.Z1-U17-DS1230Y-100.bin"
OUT="$ROOT/dyaxis/analysis/generated/ds1230"

test -f "$ROM" || { echo "missing tracked DS1230 canonical dump: $ROM" >&2; exit 2; }
python3 "$ROOT/dyaxis/analysis/analyze_ds1230.py" "$ROM" "$OUT"
PYTHONPATH="$ROOT" python3 -m unittest dyaxis.analysis.test_ds1230_analysis
