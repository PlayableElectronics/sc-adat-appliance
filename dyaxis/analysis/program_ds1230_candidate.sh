#!/bin/sh
set -eu

# Guarded operator procedure for the original Dallas DS1230Y-100.
# Default mode is validation only. No command in dry-run mode reads or writes
# the chip contents. The write modes perform only minipro -w followed by -r.

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
PROFILE='DS1230Y(RW)'
SIZE=32768
ORIGINAL="$ROOT/dyaxis/firmware/original/41.005.415.Z1-U17-DS1230Y-100.bin"
CANDIDATE="$ROOT/dyaxis/firmware/candidates/41.005.415.Z1-U17-first-app-SJMP-8000.bin"
ORIGINAL_SHA=2e58841c485f9f805c159cee5901de053ca7397c20e5c08941328b6028152ca4
CANDIDATE_SHA=cb5a4306ce73bef3b6ec76b18b367606d1a954e99d6584350c6b7ef394c9ee19
MODE=dry-run

die() { echo "ERROR: $*" >&2; exit 2; }
usage() {
    cat >&2 <<EOF
usage:
  $0 --dry-run
  $0 --write --confirm-candidate
  $0 --restore-original --confirm-original
EOF
    exit 2
}

while [ "$#" -gt 0 ]; do
    case "$1" in
        --dry-run) [ "$MODE" = dry-run ] || usage; MODE=dry-run ;;
        --write) [ "$MODE" = dry-run ] || usage; MODE=write ;;
        --restore-original) [ "$MODE" = dry-run ] || usage; MODE=restore ;;
        --confirm-candidate) [ "$MODE" = write ] || usage; CONFIRM=candidate ;;
        --confirm-original) [ "$MODE" = restore ] || usage; CONFIRM=original ;;
        *) usage ;;
    esac
    shift
done

[ -x "$(command -v minipro || true)" ] || die "minipro is not installed"
[ -f "$ORIGINAL" ] || die "missing canonical original: $ORIGINAL"
[ -f "$CANDIDATE" ] || die "missing candidate: $CANDIDATE"
[ "$(stat -f %Lp "$ORIGINAL")" = 444 ] || die "canonical original is not mode 0444"

check_image() {
    file=$1 expected=$2 label=$3
    [ "$(wc -c < "$file" | tr -d ' ')" = "$SIZE" ] || die "$label has wrong size"
    actual=$(shasum -a 256 "$file" | awk '{print $1}')
    [ "$actual" = "$expected" ] || die "$label SHA-256 $actual != $expected"
}
check_image "$ORIGINAL" "$ORIGINAL_SHA" original
check_image "$CANDIDATE" "$CANDIDATE_SHA" candidate

presence=$(minipro -k 2>&1) || die "programmer unavailable: $presence"
printf '%s\n' "$presence"
case "$presence" in
    *TL866A*|*TL866II*|*T48*|*T56*) ;;
    *) die "connected programmer was not identified as a supported Xgecu programmer" ;;
esac

info=$(minipro -d "$PROFILE" 2>&1) || die "device definition unavailable: $info"
printf '%s\n' "$info"
case "$info" in *DS1230Y\(RW\)*) ;; *) die "exact profile $PROFILE was not reported" ;; esac
case "$info" in *"32768 Bytes"*) ;; *) die "profile does not report 32768 bytes" ;; esac
case "$info" in *DIP28*) ;; *) die "profile does not report DIP28" ;; esac

echo "validated: profile=$PROFILE size=$SIZE original=$ORIGINAL_SHA candidate=$CANDIDATE_SHA"
if [ "$MODE" = dry-run ]; then
    echo "DRY RUN: no chip read, write, erase, verify, blank-check, protection, or ID operation issued"
    exit 0
fi

if [ "$MODE" = write ]; then
    [ "${CONFIRM:-}" = candidate ] || die "use --write --confirm-candidate"
    image=$CANDIDATE expected=$CANDIDATE_SHA label=candidate
    prewrite_expected=$ORIGINAL_SHA
else
    [ "${CONFIRM:-}" = original ] || die "use --restore-original --confirm-original"
    image=$ORIGINAL expected=$ORIGINAL_SHA label=original
    prewrite_expected='known-candidate-or-original'
fi

umask 077
stamp=$(date -u +%Y%m%dT%H%M%SZ)
outdir="$ROOT/.local/dyaxis/ds1230-programming-readback/$stamp"
mkdir -p "$outdir"

# Three pre-write reads are a final identity/retention gate. They remain local
# evidence and are never written over the tracked original.
for n in 1 2 3; do
    minipro -p "$PROFILE" -r "$outdir/prewrite-$n.bin"
    if [ "$prewrite_expected" = known-candidate-or-original ]; then
        current=$(shasum -a 256 "$outdir/prewrite-$n.bin" | awk '{print $1}')
        case "$current" in
            "$ORIGINAL_SHA"|"$CANDIDATE_SHA") ;;
            *) die "pre-write read $n is neither canonical original nor known candidate" ;;
        esac
    else
        check_image "$outdir/prewrite-$n.bin" "$prewrite_expected" "pre-write read $n"
    fi
done
cmp "$outdir/prewrite-1.bin" "$outdir/prewrite-2.bin" || die "pre-write reads differ"
cmp "$outdir/prewrite-1.bin" "$outdir/prewrite-3.bin" || die "pre-write reads differ"

echo "ABOUT TO WRITE $label using minipro -p '$PROFILE' -w '$image'"
minipro -p "$PROFILE" -w "$image"

minipro -p "$PROFILE" -r "$outdir/postwrite.bin"
check_image "$outdir/postwrite.bin" "$expected" "post-write readback"
cmp "$image" "$outdir/postwrite.bin" || die "post-write readback differs from $label"
echo "SUCCESS: post-write readback matches $label ($expected)"
