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

The first production mixer milestone is Debian/Docker-only:
`mixer/mixerctl.py` owns configuration and OSC policy, while
`supercollider/synthdefs/sc-adat-mixer.scd` is compiled by Debian `sclang`.
It activates only 16 confirmed ADAT channels and keeps a 24-channel data-model
capacity. It does not change Buildroot, partitions, GRUB, or `/boot`.

Chataigne is an optional external show-control and dashboard layer. It does
not process audio and is not required for mixer startup or operation. Native
SuperCollider scheduling remains available for future sample-accurate events;
this milestone adds no automation sequencer. Open Stage Control remains a
possible future specialized surface, not a dependency of the first spatial
prototype.

The intended capture contract keeps physical identity stable: all 16 raw
inputs are pre-fader/pre-processing, followed by eight pre-spatial group
stems and four post-spatial quad master channels. Timestamped OSC automation
and song markers are metadata. Song scenes may reassign physical inputs to
functional groups. Recording is deliberately outside this quad milestone;
the stable names and interfaces are reserved for a later recorder.

RME clock ownership is in the Debian audio-hardware layer, not mixer DSP.
`audio/clock.conf` declares the current `Digi9652` intent (`master`, 48 kHz),
and `scripts/audio-clock apply` is run before JACK. The later Buildroot
integration point is the audio init service after stable card detection and
before `jackd`; it will use a native equivalent of that apply/readback step.
That Buildroot integration is deliberately not part of this change.

## SC-ADAT payload ownership

The Dell has one active boot mode at a time. While Debian is booted, Codex,
the checkout, the pinned Docker development environment, sclang, JACK,
scsynth and the physical DIGI9652 are all operated locally on that Dell.
Compiled payloads are promoted to the shared data filesystem. While Buildroot
is booted, its read-only/RAM appliance mounts that filesystem, validates and
loads the compiled payload, and never compiles `.scd` or communicates with
Debian. The Mac is an SSH client only; it is not a compiler, deployment host,
or required repository location.

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
fast Debian staging against real audio hardware
    |
    v
one-shot GRUB boot of exact candidate bundle from Debian storage
    |
    v
inactive appliance slot deployment
    |
    v
slot boot, audio validation, promotion to known-good
```

The release bundle should contain the kernel, RAM-root image, optional
read-only rootfs, manifest, checksums and a generated GRUB entry fragment.
Building an artifact never grants permission to deploy it.

## Pre-release execution

A release must be runnable before it is written to an appliance slot.

### Fast Debian staging

Run the freshly built scsynth/supernova, plugins and control code against the
real DIGI9652 from a versioned staging directory. This is for rapid iteration
and validates userspace behaviour with the hardware. It uses the Debian kernel
and libraries unless an isolated target-root runner is implemented, so it
cannot validate the final kernel or complete root filesystem.

### Exact candidate boot

Create a temporary, non-default GRUB entry that loads the exact candidate
kernel and initramfs/RAM-root bundle from ordinary files on the Debian
filesystem or boot filesystem. This executes the same immutable release that
would be deployed to slot A or B, while leaving both slots untouched.

A successful candidate boot must demonstrate that the root is RAM-backed or
read-only as designed, the data partition is mounted deliberately, the RME
driver and clocking work, scsynth starts, and Debian remains recoverable.
Deployment must reuse the already-tested bundle and verify matching hashes.

## Boot model

GRUB provides:

- Debian development/recovery;
- SC-ADAT candidate (temporary, non-default, from Debian files);
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
7. Userspace passes fast Debian staging against the DIGI9652.
8. Exact candidate bundle boots through a temporary non-default GRUB entry
   without writing either appliance slot.
9. Candidate runs from the intended read-only/RAM-backed root.
10. Candidate passes audio, control, Dyaxis and recovery tests.
11. Release manifest and hashes still match before inactive-slot deployment.
12. The deployed slot reproduces the candidate result.
13. Only then may it be promoted or selected by default.
