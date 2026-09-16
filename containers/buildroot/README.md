# Buildroot builder

This pinned container is the authoritative factory for the first native
SC-ADAT candidate. It builds a self-contained x86_64 kernel and compressed
initramfs; no appliance partition is created.

From the repository root:

```sh
./lab build candidate
./lab verify candidate
```

The build runs as the invoking UID in the Dockerized Buildroot toolchain.
Downloads and intermediate output are kept under `.local/`; generated release
files are under `artifacts/sc-adat-<release>/` and include `kernel`,
`initramfs`, `kernel.config`, `manifest`, `checksums.sha256`, and
`grub-entry.cfg`.

Pinned inputs are Buildroot 2025.02.9, Linux 6.12.107, musl, and SuperCollider
3.13.0. The target includes the RME Digi9652 driver, DHCP, Dropbear SSH,
JACK2, and ordered boot services for JACK then scsynth.

Dropbear accepts root authentication only through the public key in the
ignored `.local/appliance/authorized_keys` input. The build fails clearly when
that file is absent; never place its private key in the repository.

Candidate staging and boot preparation are deliberately separate and dry-run
only. Use `./lab stage candidate --dry-run` and
`./lab boot candidate --dry-run` to review the exact files and commands; no
GRUB, boot variable, partition, or block-device operation is performed by the
builder.
