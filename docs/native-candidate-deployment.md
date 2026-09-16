# Native candidate deployment gate

The first candidate is a kernel plus initramfs loaded from Debian's existing
filesystem. Build and verification do not require root. No command in this
document has been run by the candidate build.

## Exact proposed files

For `SC_ADAT_RELEASE_ID=candidate-1`, copy these generated files:

```text
artifacts/sc-adat-candidate-1/kernel             -> /boot/sc-adat/candidate-1/kernel
artifacts/sc-adat-candidate-1/initramfs          -> /boot/sc-adat/candidate-1/initramfs
artifacts/sc-adat-candidate-1/kernel.config      -> /boot/sc-adat/candidate-1/kernel.config
artifacts/sc-adat-candidate-1/manifest           -> /boot/sc-adat/candidate-1/manifest
artifacts/sc-adat-candidate-1/checksums.sha256   -> /boot/sc-adat/candidate-1/checksums.sha256
artifacts/sc-adat-candidate-1/grub-entry.cfg     -> /boot/sc-adat/candidate-1/grub-entry.cfg
artifacts/sc-adat-candidate-1/grub-entry.cfg     -> /etc/grub.d/42-sc-adat-candidate
```

The proposed GRUB entry is:

```grub
menuentry 'SC-ADAT candidate-1 (one-shot candidate)' --id sc-adat-candidate-1 {
    insmod part_gpt
    insmod ext2
    search --no-floppy --file --set=root /boot/sc-adat/candidate-1/kernel
    linux /boot/sc-adat/candidate-1/kernel console=tty0 console=ttyS0,115200n8 root=/dev/ram0 rdinit=/sbin/init
    initrd /boot/sc-adat/candidate-1/initramfs
}
```

## Exact proposed commands

The commands below are the complete proposed transition. They are not run by
the current gate. `DEBIAN_STABLE_ID` must be replaced by the exact stable ID
reported by read-only host preflight; it must never be guessed.

From any working directory, set `REPO_ROOT` to the absolute repository path,
then after explicit approval and only after reviewing the dry-run output:

```sh
REPO_ROOT=/absolute/path/to/sc-adat-appliance
ART="$REPO_ROOT/artifacts/sc-adat-candidate-1"
sudo install -D -m 0644 "$ART/kernel" /boot/sc-adat/candidate-1/kernel
sudo install -D -m 0644 "$ART/initramfs" /boot/sc-adat/candidate-1/initramfs
sudo install -D -m 0644 "$ART/kernel.config" /boot/sc-adat/candidate-1/kernel.config
sudo install -D -m 0644 "$ART/manifest" /boot/sc-adat/candidate-1/manifest
sudo install -D -m 0644 "$ART/checksums.sha256" /boot/sc-adat/candidate-1/checksums.sha256
sudo install -D -m 0644 "$ART/grub-entry.cfg" /boot/sc-adat/candidate-1/grub-entry.cfg
sudo install -D -m 0755 "$ART/grub-entry.cfg" /etc/grub.d/42-sc-adat-candidate
sudo install -D -m 0644 /dev/stdin /etc/default/grub.d/90-sc-adat-candidate <<'EOF'
GRUB_DEFAULT=saved
GRUB_SAVEDEFAULT=false
EOF
sudo grub-editenv /boot/grub/grubenv set saved_entry=DEBIAN_STABLE_ID
TMP_CFG=$(mktemp)
trap 'rm -f "$TMP_CFG"' EXIT
sudo grub-mkconfig -o "$TMP_CFG"
sudo grub-script-check "$TMP_CFG"
test "$(grep -c -- "--id sc-adat-candidate-1" "$TMP_CFG")" -eq 1
test "$(grep -c "menuentry 'SC-ADAT candidate-1" "$TMP_CFG")" -eq 1
grep -q 'next_entry' "$TMP_CFG"
test "$(sudo grub-editenv /boot/grub/grubenv list | grep -c '^saved_entry=DEBIAN_STABLE_ID$')" -eq 1
sudo install -m 0644 "$TMP_CFG" /boot/grub/grub.cfg
sudo grub-reboot sc-adat-candidate-1
sudo reboot
```

These commands do not select a disk or modify a partition. The deployment
script must be reviewed and explicitly enabled before use.

## One-shot behavior and rollback

The minimal persistent transition is `GRUB_DEFAULT=saved` and
`GRUB_SAVEDEFAULT=false`, with Debian's exact stable ID explicitly written as
`saved_entry` before selecting the candidate. This keeps Debian persistent
while `grub-reboot sc-adat-candidate-1` sets only `next_entry`. Verify that the
generated `grub.cfg` contains its normal `next_entry` handling and that
`grub-editenv list` shows Debian as `saved_entry` before reboot.

The one-shot variable behavior can be checked without touching the host
environment:

```sh
TEST_ENV=$(mktemp)
grub-editenv "$TEST_ENV" create
grub-editenv "$TEST_ENV" set next_entry=sc-adat-candidate-1
test "$(grub-editenv "$TEST_ENV" list | grep -c '^next_entry=sc-adat-candidate-1$')" -eq 1
grub-editenv "$TEST_ENV" unset next_entry
test "$(grub-editenv "$TEST_ENV" list | grep -c '^next_entry=')" -eq 0
```

To clear a pending one-shot selection before reboot, use:

```sh
sudo grub-editenv /boot/grub/grubenv unset next_entry
```

To roll back before or after a failed candidate boot, first clear
`next_entry`, restore the previous `/etc/default/grub` contents, restore the
previous `saved_entry`, remove only `/etc/grub.d/42-sc-adat-candidate` and
`/boot/sc-adat/candidate-1`, and regenerate `grub.cfg` through a temporary
file followed by `grub-script-check`. Debian files and partitions are not
removed.
After a failed candidate boot, select Debian from the firmware/GRUB menu or
allow the one-shot selection to expire, then remove the candidate files and
entry from Debian.

Use `./lab stage candidate --dry-run` and `./lab boot candidate --dry-run` to
print the current release-specific proposal. The reviewed apply path is
`sudo ./candidates/deploy-grub-candidate.sh --apply`; it stages the exact
candidate, regenerates and checks GRUB, preserves Debian as `saved_entry`, sets
the candidate as `next_entry`, verifies deployed checksums, and does not reboot.

## Console diagnostics

The kernel command line contains `console=tty0 console=ttyS0,115200n8`.
`tty0` supplies visible boot diagnostics on the monitor. `tty1` is the
physically accessible recovery console and starts a shell after boot; `ttyS0`
also carries the serial getty and diagnostics. The final report is printed on
both `tty0` and `ttyS0` and remains above the recovery prompt. It is saved as
`/var/log/sc-adat-boot-report.log`.

## In-appliance self-test

After every service has either started or failed, `S99diagnostics` runs the
single automatic boot report. It checks kernel RT mode, AF_PACKET, SysV IPC,
`/dev/shm`, display and USB input, loopback, Ethernet/DHCP, Dropbear policy,
Digi9652/ALSA channels, JACK parser/runtime settings/realtime scheduling/
physical ports/xruns, and scsynth liveness/readiness/ports. It includes exact
commands, process scheduling data, JACK port names, ALSA cards, addresses and
failure-log tails. Supporting logs are `/var/log/kernel-probes.log`,
`/var/log/dhcpcd.log`, `/var/log/jack.log`, `/var/log/scsynth.log`, and
`/var/log/boot-diagnostics.log`.

```text
FINAL RESULT: PASS (0 failed)
```

QEMU validates the kernel, initramfs, console, report ordering, bounded
no-network boot, kernel probes, and failure-report path. QEMU cannot emulate
the physical RME Digi9652, so Digi9652 detection, 26-channel ALSA parameters,
JACK runtime topology/realtime thread, and scsynth 26-port readiness remain
explicit hardware-only checks in the report.

After the candidate has booted, the exact commands are:

```sh
# From Debian, select the prepared candidate for one boot and reboot:
sudo grub-reboot sc-adat-candidate-1
sudo reboot

# Determine the candidate DHCP address from the serial console, DHCP lease
# table, or the boot diagnostics shown below, then connect:
ssh root@<candidate-dhcp-address>

# From the Debian host, retrieve the boot report and related logs:
scp root@<candidate-dhcp-address>:/var/log/sc-adat-boot-report.log \
  root@<candidate-dhcp-address>:/var/log/boot-diagnostics.log \
  root@<candidate-dhcp-address>:/var/log/jack.log \
  root@<candidate-dhcp-address>:/var/log/scsynth.log .local/appliance/

# If the candidate is running and must be selected again for a subsequent
# controlled boot, use the same stable ID (this is not persistent defaulting):
sudo grub-reboot sc-adat-candidate-1
```

The deployment helper sets `next_entry` and stops before reboot; the remaining
operator action is `sudo reboot` after reviewing the automatic report policy.

## SSH access (development-only policy)

Dropbear password authentication and root login are intentionally enabled for
temporary diagnostics on a trusted local network. No
`.local/appliance/authorized_keys` file is required or included. After DHCP,
connect with:

```sh
ssh root@<candidate-dhcp-address>
```

Use the temporary diagnostic password `scadat`. This is development-only
policy and must be removed before production deployment.

The address is available from the DHCP lease table, the serial console, or
`/var/log/boot-diagnostics.log` (`ip -brief addr`).
