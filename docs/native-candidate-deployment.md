# Native candidate deployment gate

The first candidate is a kernel plus initramfs loaded from Debian's existing
filesystem. Build and verification do not require root. No command in this
document has been run by the candidate build.

## Exact proposed files

For `SC_ADAT_RELEASE_ID=candidate-1`, copy these generated files:

```text
artifacts/sc-adat-candidate-1/kernel             -> /boot/sc-adat/candidate-1/kernel
artifacts/sc-adat-candidate-1/initramfs          -> /boot/sc-adat/candidate-1/initramfs
artifacts/sc-adat-candidate-1/manifest           -> /boot/sc-adat/candidate-1/manifest
artifacts/sc-adat-candidate-1/checksums.sha256   -> /boot/sc-adat/candidate-1/checksums.sha256
```

The proposed GRUB entry is:

```grub
menuentry 'SC-ADAT candidate-1 (one-shot candidate)' {
    insmod part_gpt
    insmod ext2
    search --no-floppy --file --set=root /boot/sc-adat/candidate-1/kernel
    linux /boot/sc-adat/candidate-1/kernel console=ttyS0,115200n8 root=/dev/ram0 rdinit=/sbin/init
    initrd /boot/sc-adat/candidate-1/initramfs
}
```

## Exact proposed commands

After explicit approval, and only after reviewing the dry-run output:

```sh
sudo install -D -m 0644 artifacts/sc-adat-candidate-1/kernel /boot/sc-adat/candidate-1/kernel
sudo install -D -m 0644 artifacts/sc-adat-candidate-1/initramfs /boot/sc-adat/candidate-1/initramfs
sudo install -D -m 0644 artifacts/sc-adat-candidate-1/manifest /boot/sc-adat/candidate-1/manifest
sudo install -D -m 0644 artifacts/sc-adat-candidate-1/checksums.sha256 /boot/sc-adat/candidate-1/checksums.sha256
sudo install -D -m 0755 artifacts/sc-adat-candidate-1/grub-entry.cfg /etc/grub.d/42-sc-adat-candidate
sudo grub-mkconfig -o /boot/grub/grub.cfg
sudo grub-reboot 'SC-ADAT candidate-1 (one-shot candidate)'
sudo reboot
```

These commands do not select a disk or modify a partition. The deployment
script must be reviewed and explicitly enabled before use.

## One-shot behavior and rollback

`grub-reboot` selects only the next boot. Debian remains the persistent default:
do not change `GRUB_DEFAULT` and do not use `grub-set-default`. If the
candidate has not been booted, remove the four candidate files and
`/etc/grub.d/42-sc-adat-candidate`, then regenerate `grub.cfg`. To clear a
pending one-shot selection before reboot, use the distribution's
`grub-editenv /boot/grub/grubenv unset next_entry`.
After a failed candidate boot, select Debian from the firmware/GRUB menu or
allow the one-shot selection to expire, then remove the candidate files and
entry from Debian.

Use `./lab stage candidate --dry-run` and `./lab boot candidate --dry-run` to
print the current release-specific proposal. The commands intentionally stop
at this deployment gate.
