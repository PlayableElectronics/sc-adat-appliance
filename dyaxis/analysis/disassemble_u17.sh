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

mkdir -p "$OUT"
TMP="$OUT/.u17.reachable.asm.tmp"
trap 'rm -f "$TMP"' EXIT HUP INT TERM
"$DISASM" \
  --include "$ROOT/dyaxis/analysis/p80c552.mcu" \
  --entry RESET --entry EXT0 --entry TIMER0 --entry EXT1 --entry TIMER1 \
  --entry SIO0_UART --entry SIO1_I2C --entry T2_CAPTURE0 --entry T2_CAPTURE1 \
  --entry T2_CAPTURE2 --entry T2_CAPTURE3 --entry ADC_COMPLETE \
  --entry T2_COMPARE0 --entry T2_COMPARE1 --entry T2_COMPARE2 --entry T2_OVERFLOW \
  "$ROM" > "$TMP"
sed "s#$(printf '%s' "$ROOT" | sed 's/[.[\*^$()+?{|\\]/\\&/g')#<repository>#g" "$TMP" > "$OUT/u17.reachable.asm"
