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
sudo ./lab payload promote --data-root /data/sc-adat
one-shot boot Buildroot
```

The Buildroot boot service never compiles `.scd`: it discovers the filesystem
by the `SC_ADAT_DATA` label, mounts `/data` read-only, verifies `current`,
loads compiled SynthDefs through `/usr/bin/sc-adat-osc-loader`, and falls back
to `previous` and then the immutable factory payload. Payload files are
immutable after promotion. `current` and `previous` are relative symlinks
replaced with temporary symlinks and `mv`; `sessions/` is writable reserved
space and is excluded from release validation.

The fixture contract is:

```text
/data/sc-adat/releases/<version>/{synthdefs,config,scripts,VERSION,manifest.sha256,metadata.json}
/data/sc-adat/{current,previous}
```

The shared partition is `SC_ADAT_DATA`, ext4, mounted at `/data`; only
`/data/sc-adat` is owned by this project. Debian mounts it read-write by UUID;
Buildroot discovers the label and mounts it read-only. Backup must copy
complete versioned releases and both symlinks, verify `manifest.sha256` after
restore, and keep at least one known-good release before deleting old versions.
The installed partition is 96 GiB and leaves the remaining SSD space
unallocated. Its Debian fstab entry is UUID-based with `nofail` and a bounded
device timeout. `sessions/` remains writable for future recordings and is
never included in release manifests. Buildroot does not run fsck automatically
and continues with the immutable factory payload when the filesystem is absent,
unmountable or invalid.

The full Buildroot rebuild gate applies only to kernel, drivers, JACK/scsynth,
libc/toolchain, base utilities, and boot/mount/network/recovery infrastructure.
SynthDefs, mixer graphs, effects, routing, OSC mappings, presets, loopers and
Dyaxis mappings are payload data and do not require a full Buildroot rebuild.
