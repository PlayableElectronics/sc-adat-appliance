#!/bin/sh
set -eu

# Read-only post-boot evidence acquisition. Never writes, erases, verifies,
# blank-checks, protects, unprotects, or reads device ID.
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
PROFILE='DS1230Y(RW)'
ORIGINAL="$ROOT/dyaxis/firmware/original/41.005.415.Z1-U17-DS1230Y-100.bin"
CANDIDATE="$ROOT/dyaxis/firmware/candidates/41.005.415.Z1-U17-first-app-SJMP-8000.bin"
umask 077
stamp=$(date -u +%Y%m%dT%H%M%SZ)
outdir="$ROOT/.local/dyaxis/ds1230-postboot/$stamp"
mkdir -p "$outdir"

for n in 1 2 3; do
    minipro -p "$PROFILE" -r "$outdir/read-$n.bin"
    test "$(wc -c < "$outdir/read-$n.bin" | tr -d ' ')" = 32768
done
cmp "$outdir/read-1.bin" "$outdir/read-2.bin"
cmp "$outdir/read-1.bin" "$outdir/read-3.bin"

python3 - "$outdir" "$ORIGINAL" "$CANDIDATE" <<'PY'
import hashlib, pathlib, sys
out, original, candidate = map(pathlib.Path, sys.argv[1:])
data = (out / "read-1.bin").read_bytes()
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def ranges(changes):
    result=[]
    for i in changes:
        if not result or i != result[-1][-1] + 1: result.append([i])
        else: result[-1].append(i)
    return ", ".join(f"0x{x[0]:04X}-0x{x[-1]:04X}" for x in result) or "none"
print(f"directory: {out}")
print(f"postboot-sha256: {hashlib.sha256(data).hexdigest()}")
for label, path in (("original", original), ("candidate", candidate)):
    ref = path.read_bytes()
    changed = [i for i,(a,b) in enumerate(zip(data, ref)) if a != b]
    print(f"vs-{label}: {len(changed)} changed bytes; ranges: {ranges(changed)}")
    if len(changed) <= 32:
        for i in changed: print(f"  0x{i:04X}: {ref[i]:02X}->{data[i]:02X}")
PY
