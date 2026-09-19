#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
ROM=${1:-"$ROOT/dyaxis/firmware/original/41.005.415.Z1-U17-V1.06-AM27C256.bin"}
OUT=${2:-"$ROOT/dyaxis/analysis/generated/u17"}
DISASM=${DISASM51_BIN:-"$ROOT/.local/disasm51-venv/bin/disasm51"}

[ -x "$DISASM" ] || { echo "missing disasm51: $DISASM" >&2; exit 2; }
[ -f "$ROM" ] || { echo "missing ROM: $ROM" >&2; exit 2; }
[ "$(wc -c < "$ROM" | tr -d ' ')" = 32768 ] || { echo "wrong ROM size" >&2; exit 2; }
HASH=$(shasum -a 256 "$ROM" | awk '{print $1}')
[ "$HASH" = 22aa7788f49abf0c5ad31d0bc15fb2048cacaec1bac8cec0ddde87e29854e0dd ] || { echo "wrong ROM SHA-256" >&2; exit 2; }
DS1230="$ROOT/dyaxis/firmware/original/41.005.415.Z1-U17-DS1230Y-100.bin"
[ -f "$DS1230" ] || { echo "missing DS1230 dump: $DS1230" >&2; exit 2; }
[ "$(wc -c < "$DS1230" | tr -d ' ')" = 32768 ] || { echo "wrong DS1230 size" >&2; exit 2; }

# The preserved DS1230 FE00..FE7F table is an authoritative set of additional
# U17 CODE entry points. Numeric entries are passed explicitly; no bytes are
# promoted to code merely because they are non-zero.
TRAMP_ENTRIES=$(python3 - "$DS1230" <<'PY'
from pathlib import Path
import sys
d = Path(sys.argv[1]).read_bytes()
targets = []
for off in range(0x7E00, 0x7E81, 3):
    if d[off] == 0x02:
        targets.append(f"--entry=0x{d[off+1]:02X}{d[off+2]:02X}")
print(" ".join(targets))
PY
)
python3 - "$DS1230" "$OUT/u17-ds1230-trampoline-seeds.tsv" <<'PY'
from pathlib import Path
import sys
d = Path(sys.argv[1]).read_bytes()
out = ["cpu_address\tfile_offset\tu17_code_target\n"]
for off in range(0x7E00, 0x7E81, 3):
    if d[off] == 0x02:
        cpu = off + 0x8000
        target = (d[off + 1] << 8) | d[off + 2]
        out.append(f"0x{cpu:04X}\t0x{off:04X}\t0x{target:04X}\n")
Path(sys.argv[2]).write_text("".join(out), encoding="utf-8")
PY

mkdir -p "$OUT"
TMP="$OUT/.u17.reachable.asm.tmp"
trap 'rm -f "$TMP"' EXIT HUP INT TERM
"$DISASM" \
  --include "$ROOT/dyaxis/analysis/p80c552.mcu" \
  --entry RESET --entry EXT0 --entry TIMER0 --entry EXT1 --entry TIMER1 \
  --entry SIO0_UART --entry SIO1_I2C --entry T2_CAPTURE0 --entry T2_CAPTURE1 \
  --entry T2_CAPTURE2 --entry T2_CAPTURE3 --entry ADC_COMPLETE \
  --entry T2_COMPARE0 --entry T2_COMPARE1 --entry T2_COMPARE2 --entry T2_OVERFLOW \
  $TRAMP_ENTRIES \
  "$ROM" > "$TMP"
sed "s#$(printf '%s' "$ROOT" | sed 's/[.[\*^$()+?{|\\]/\\&/g')#<repository>#g" "$TMP" > "$OUT/u17.reachable.asm"
