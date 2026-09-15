# Architecture

## Three machine identities

### Debian factory and recovery host

A normal writable Debian installation provides:

- Docker Engine;
- Git and Codex;
- hardware inspection and diagnostic tools;
- GRUB, filesystem and deployment utilities;
- access to the RME DIGI9652, USB programmers and Dyaxis Nano bridge;
- recovery when an appliance image fails.

Debian should remain lean. Compiler suites, FPGA vendor tools, MCU SDKs and
Buildroot dependencies belong in containers rather than the host filesystem.

### Containerized build laboratory

Docker containers provide pinned, headless toolchains. The authoritative
Buildroot container builds the complete appliance release. Other planned
containers cover SuperCollider development, Arduino AVR, Daisy/ARM, RP2040,
iCE40/iCEBreaker, legacy Spartan-6/Mojo ISE and offline audio analysis.

Containers use a common contract:

```text
/work       source checkout
/cache      downloadable and compiler caches
/artifacts  immutable build outputs
```

They run with the invoking user's UID/GID. Generated artifacts must not become
root-owned. Toolchain versions and base images are pinned once validated.

Containers compile, link, simulate, test and package. The Debian host owns
physical deployment: USB flashing, GRUB configuration and appliance-slot
writes. A narrowly scoped interactive container may receive a specific USB
device only when required and explicitly selected.

### RAM-resident appliance

GRUB boots an immutable Buildroot release directly, without Docker. The release
contains:

- validated Linux kernel with `snd-rme9652`;
- read-only compressed root filesystem or initramfs;
- tmpfs for `/run`, `/tmp`, logs and other transient writes;
- scsynth and initially supernova;
- selected plugins and SynthDefs;
- Dyaxis ADB USB-serial bridge and future surface host emulator;
- OSC/control daemon, supervision and health reporting.

Persistent configuration, calibration, approved recordings, loops and
SynthDefs live on the shared data filesystem. The exact RAM-root mechanism
(initramfs-only, copied SquashFS, or equivalent) remains a measured
implementation choice.

## Data flow

```text
norns / Dyaxis -- OSC/control --> scsynth appliance -- PCI --> DIGI9652 -- ADAT
```

## Build and release flow

```text
Git checkout
    |
    v
pinned Buildroot container
    |
    v
versioned release bundle in /artifacts
    |
    v
host-side validation and checksum verification
    |
    v
inactive appliance slot + GRUB entry
    |
    v
test boot, audio validation, promotion to known-good
```

The release bundle should contain the kernel, RAM-root image, optional
read-only rootfs, manifest, checksums and a generated GRUB entry fragment.
Building an artifact never grants permission to deploy it.

## Boot model

GRUB provides:

- Debian development/recovery;
- SC-ADAT slot A;
- SC-ADAT slot B.

A new image is written only to an inactive slot. The running slot and
last-known-good slot are never overwritten. Debian remains the default until a
candidate passes boot, recovery and audio validation.

The concrete disk layout is deferred until the target reports SSD size,
partition table, firmware boot mode and current installation.

## Validation gates

1. DIGI9652 detected by `snd-rme9652`.
2. Stable playback on every required ADAT channel.
3. Clock source and lock state verified.
4. Baseline latency and xrun measurements recorded.
5. Headless SuperCollider build validated.
6. Buildroot container produces the release reproducibly.
7. Release manifest and checksums match the deployed candidate.
8. Candidate boots without altering Debian or the known-good slot.
9. Candidate runs from the intended read-only/RAM-backed root.
10. Candidate passes audio, control, Dyaxis and recovery tests.
11. Only then may it be promoted or selected by default.
