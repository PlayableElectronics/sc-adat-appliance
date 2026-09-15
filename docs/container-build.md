# Containerized build laboratory

## Policy

Debian is the factory floor, not the toolchain image. Docker provides isolated,
versioned build environments; the Buildroot output is a separate native Linux
system that boots from GRUB.

The final audio appliance never runs inside Docker and does not include Docker.

## Planned containers

| Container | Responsibility |
|---|---|
| `buildroot` | Authoritative kernel, rootfs and appliance release bundle |
| `sc-development` | Fast SuperCollider/plugin builds and non-hardware tests |
| `arduino-avr` | Dyaxis Arduino Nano firmware |
| `daisy-arm` | Daisy Seed and libDaisy |
| `rp2040` | Pico SDK and MicroPython |
| `ice40` | Yosys, nextpnr and IceStorm for iCEBreaker |
| `mojo-ise` | Frozen amd64 Xilinx ISE environment for Spartan-6/Mojo |
| `audio-analysis` | Python DSP, capture inspection and regression analysis |

Only `buildroot` defines an appliance release. A binary produced by
`sc-development` is useful for iteration but is not automatically releasable.

## Mount contract

```text
/work       read/write source tree
/cache      disposable persistent caches
/artifacts  versioned outputs
```

Never write downloads, compiler caches or generated images into Git. Run with
the host UID/GID. Do not use broad privileged mode. Pass a specific USB device
only for a deliberate flashing session.

## Buildroot output contract

A release is staged as:

```text
artifacts/sc-adat-<release-id>/
├── kernel
├── initramfs
├── rootfs.squashfs        # when the selected RAM-root design uses it
├── manifest
├── checksums.sha256
└── grub-entry.cfg
```

Names may be refined after the first real build, but the bundle must remain
self-describing and verifiable. It records source revision, container digest,
Buildroot/Linux/SuperCollider versions and hashes of boot artifacts.

## Runtime boundary

Buildroot packages and installs scsynth/supernova, plugins, SynthDefs, Dyaxis
services and their runtime libraries into the target root filesystem. Nothing
is copied ad hoc from the Debian host during release packaging.

For quick hardware experiments, Debian may execute a staged native binary
against ALSA. Record that binary's provenance. Success there is a development
gate, not proof that the Buildroot image works.

## Deployment boundary

The container never writes partitions or edits the live GRUB configuration.
Host-side deployment tooling must:

1. resolve the active root, candidate slot and known-good slot;
2. display devices, filesystems and UUIDs;
3. verify the release manifest and checksums;
4. require explicit user approval before destructive writes;
5. write only the inactive slot;
6. add or update a non-default GRUB test entry;
7. retain a working Debian and known-good boot path.

## Version policy

Do not pin arbitrary “latest” versions before target inspection. Once the
baseline and dependency build succeed, record exact:

- container base image digest;
- Buildroot release/commit;
- Linux release and configuration hash;
- SuperCollider release/commit and build flags;
- plugin revisions;
- host architecture and release-bundle format.
