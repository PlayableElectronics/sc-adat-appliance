#!/bin/sh
set -eu

target="$1"
key_file="${SC_ADAT_PUBLIC_KEY_FILE:-/work/.local/appliance/authorized_keys}"
if test ! -s "$key_file"; then
    echo "ERROR: missing appliance public key: $key_file" >&2
    echo "Create an authorized_keys file at that ignored local path and rebuild." >&2
    exit 1
fi
if ! grep -Eq '^(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp256|ecdsa-sha2-nistp384|ecdsa-sha2-nistp521) ' "$key_file"; then
    echo "ERROR: appliance public key is not a supported authorized_keys line: $key_file" >&2
    exit 1
fi
mkdir -p "$target/etc" "$target/var/log" "$target/run" "$target/root/.ssh"
chmod 0700 "$target/root/.ssh"
rm -f "$target/etc/sc-adat-release"
printf '%s\n' 'candidate' > "$target/etc/sc-adat-release"
chmod 0444 "$target/etc/sc-adat-release"
install -m 0600 "$key_file" "$target/root/.ssh/authorized_keys"
# tty1 is a physically gated recovery shell; lock the root password hash.
sed -i 's/^root:[^:]*:/root:!:/' "$target/etc/shadow"
# This board overlay owns DHCP startup. Remove Buildroot's generated launchers
# so exactly one dhcpcd instance can exist.
rm -f "$target/etc/init.d/S40network" "$target/etc/init.d/S41dhcpcd"
