#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
ROM=${1:-"$ROOT/dyaxis/firmware/original/41.005.415.Z1-U17-V1.06-AM27C256.bin"}
OUT=${2:-"$ROOT/dyaxis/analysis/generated/u17"}
"$ROOT/dyaxis/analysis/disassemble_u17.sh" "$ROM" "$OUT"
python3 "$ROOT/dyaxis/analysis/report_u17.py" \
  "$OUT/u17.reachable.asm" "$OUT"
python3 "$ROOT/dyaxis/analysis/deep_u17_analysis.py" \
  "$OUT/u17.reachable.asm" "$ROM" "$OUT"
