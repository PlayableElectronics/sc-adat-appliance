# Architecture

## Operating modes

### Debian

Writable development, build, test, and rescue environment. It hosts Codex, Git,
the Buildroot checkout, compiler caches, diagnostic tools, and deployment tools.

### Appliance

Read-only Buildroot system dedicated to network control and real-time audio. It
contains the minimum validated runtime needed for the RME DIGI9652 and
SuperCollider.

## Data flow

```text
norns -- OSC/Ethernet --> SuperCollider appliance -- PCI --> DIGI9652 -- ADAT
```

## Release model

Two immutable appliance slots are planned. A new image is written only to the
inactive slot. The currently running slot and the last-known-good slot are never
overwritten. Debian remains available through GRUB for recovery.

The concrete disk layout is deferred until the target reports its SSD size,
partition table, firmware boot mode, and current Debian installation.

## Validation gates

1. DIGI9652 detected by `snd-rme9652`.
2. Stable playback on every required ADAT channel.
3. Clock source and lock state verified.
4. Baseline latency and xrun measurements recorded.
5. Headless SuperCollider build validated on Debian.
6. Buildroot package builds reproducibly.
7. Candidate appliance boots without altering Debian.
8. Candidate passes audio and recovery tests.
9. Only then may it become the GRUB default.
