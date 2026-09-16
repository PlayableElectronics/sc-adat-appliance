#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
RELEASE=${SC_ADAT_RELEASE_ID:-candidate-1}
ART="$ROOT/artifacts/sc-adat-$RELEASE"
DEST="/boot/sc-adat/$RELEASE"
GENERATOR=/etc/grub.d/42-sc-adat-candidate
GRUBENV=/boot/grub/grubenv
usage() { echo "Usage: $0 [--dry-run|--apply]"; }
mode=${1:---dry-run}
test "$mode" = --dry-run || test "$mode" = --apply || { usage >&2; exit 2; }
for f in kernel initramfs kernel.config manifest checksums.sha256 grub-entry.cfg; do test -s "$ART/$f" || { echo "missing artifact: $ART/$f" >&2; exit 1; }; done
stable=$(grub-editenv "$GRUBENV" list | sed -n 's/^saved_entry=//p')
test -n "$stable" || { echo 'saved_entry is empty; refusing deployment' >&2; exit 1; }
grep -Fq -- "$stable" /boot/grub/grub.cfg || { echo "saved Debian entry not present: $stable" >&2; exit 1; }
cat <<EOF
SC-ADAT deployment target (resolved read-only preflight)
  root filesystem: /dev/sda1 ext4 (active /)
  artifact:        $ART
  slot:            $DEST
  GRUB generator:  $GENERATOR
  GRUB environment: $GRUBENV
  Debian saved_entry: $stable
  candidate next_entry: sc-adat-$RELEASE
EOF
if test "$mode" = --dry-run; then
  echo 'DRY RUN — no files, grub.cfg, or grubenv will be changed.'
  exit 0
fi
test "$(id -u)" -eq 0 || { echo '--apply must run as root or via sudo' >&2; exit 1; }
(cd "$ART" && sha256sum -c checksums.sha256)
install -d -m 0755 "$DEST"
for f in kernel initramfs kernel.config manifest checksums.sha256 grub-entry.cfg; do install -D -m 0644 "$ART/$f" "$DEST/$f"; done
install -D -m 0755 "$ART/grub-entry.cfg" "$GENERATOR"
install -D -m 0644 /dev/stdin /etc/default/grub.d/90-sc-adat-candidate <<'EOF'
GRUB_DEFAULT=saved
GRUB_SAVEDEFAULT=false
EOF
tmp=$(mktemp /boot/grub/grub.cfg.sc-adat-candidate-1.XXXXXX)
trap 'rm -f "$tmp"' EXIT
grub-mkconfig -o "$tmp"
grub-script-check "$tmp"
test "$(grep -c -- "--id sc-adat-$RELEASE" "$tmp")" -eq 1
test "$(grep -c "menuentry 'SC-ADAT $RELEASE" "$tmp")" -eq 1
install -m 0644 "$tmp" /boot/grub/grub.cfg
grub-editenv "$GRUBENV" set "saved_entry=$stable" "next_entry=sc-adat-$RELEASE"
(cd "$DEST" && sha256sum -c checksums.sha256)
test "$(grub-editenv "$GRUBENV" list | grep -c "^saved_entry=$stable$")" -eq 1
test "$(grub-editenv "$GRUBENV" list | grep -c "^next_entry=sc-adat-$RELEASE$")" -eq 1
echo "STAGED: $RELEASE; Debian remains saved_entry; no reboot performed."
