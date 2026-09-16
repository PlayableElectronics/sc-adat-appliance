# Payload workflow

The Dell is operated in one boot mode at a time. Codex, the repository,
Docker, sclang, JACK, scsynth and the physical Digi9652 all run on the Dell
while Debian is booted. The Mac is only an SSH client and is not required for
building or deploying payloads.

Daily workflow, all commands below run on the Dell in Debian:

```text
boot Debian
./lab dev build                 # only after Docker dependencies change
./lab dev start
./lab dev test                  # JACK/scsynth + physical-card checks
./lab payload build             # pinned sclang; compiled bundle
./lab payload test              # real compile/load/NRT checks
./lab payload inspect
sudo ./lab payload promote --data-root /mnt/sc-adat
one-shot boot Buildroot
```

Buildroot never compiles `.scd`. It mounts the future data filesystem at
`/data`, verifies `current`, loads the compiled SynthDefs through the stable
OSC loader (`/done` or `/fail`, then `/sync` and `/synced`), and falls back to
`previous` and then a factory payload. Payload files are immutable after
promotion. `current` and `previous` are relative symlinks replaced with
temporary symlinks and `mv`; no Buildroot, GRUB or reboot command is called by
payload build/test/promote.

The fixture contract is:

```text
/data/sc-adat/releases/<version>/{synthdefs,config,scripts,VERSION,manifest.sha256,metadata.json}
/data/sc-adat/{current,previous}
```

The future partition is labelled `SC_ADAT_DATA`, ext4, mounted at `/data`, and
only `/data/sc-adat` is owned by this project. It should be a few GiB, leaving
the remaining SSD unallocated for future use. Debian will mount it by label or
UUID in its reviewed mount configuration; Buildroot will use the same label or
UUID and never `/dev/sdX` enumeration. Backup must copy complete versioned
releases and both symlinks, verify `manifest.sha256` after restore, and keep at
least one known-good release before deleting old versions. This task creates
or formats no partition.

The full Buildroot rebuild gate applies only to kernel, drivers, JACK/scsynth,
libc/toolchain, base utilities, and boot/mount/network/recovery infrastructure.
SynthDefs, mixer graphs, effects, routing, OSC mappings, presets, loopers and
Dyaxis mappings are payload data and do not require a full Buildroot rebuild.
