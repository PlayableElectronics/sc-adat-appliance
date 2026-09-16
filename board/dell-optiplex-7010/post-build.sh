#!/bin/sh
set -eu

target="$1"
mkdir -p "$target/var/log" "$target/run" "$target/root/.ssh"
chmod 0700 "$target/root/.ssh"
rm -f "$target/etc/sc-adat-release"
printf '%s\n' 'candidate' > "$target/etc/sc-adat-release"
chmod 0444 "$target/etc/sc-adat-release"
