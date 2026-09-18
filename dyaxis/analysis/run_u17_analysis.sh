#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
"$ROOT/dyaxis/analysis/disassemble_u17.sh" "$@"
python3 "$ROOT/dyaxis/analysis/report_u17.py" \
  "$ROOT/dyaxis/analysis/generated/u17/u17.reachable.asm" \
  "$ROOT/dyaxis/analysis/generated/u17"
