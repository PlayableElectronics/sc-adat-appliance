#!/bin/sh
set -eu

target="$1"
mkdir -p "$target/etc" "$target/var/log" "$target/run"
rm -f "$target/etc/sc-adat-release"
printf '%s\n' 'candidate' > "$target/etc/sc-adat-release"
chmod 0444 "$target/etc/sc-adat-release"
# Development-only policy: temporary password is exactly scadat.
rm -rf "$target/root/.ssh"
sed -i 's#^root:[^:]*:#root:$6$scadat$19wixirItRBedtix3jaBZqEZUNuW4uZal3srNDITblzBgzk1ouJ934zvvTskkCnWMarDY7tTQ2YvdXAfYyX/F0:#' "$target/etc/shadow"
# This board overlay owns DHCP startup. Remove Buildroot's generated launchers
# so exactly one dhcpcd instance can exist.
rm -f "$target/etc/init.d/S40network" "$target/etc/init.d/S41dhcpcd"
