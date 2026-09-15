# sc-adat-appliance

A reproducible, headless SuperCollider audio appliance for a Dell OptiPlex 7010
with an original RME DIGI9652 (Project Hammerfall) PCI interface.

## Goal

Use writable Debian as a lean development, diagnostic and recovery host. Docker
provides reproducible toolchains; its authoritative Buildroot container builds
the complete SuperCollider appliance OS. GRUB boots that immutable system
natively for low-latency performance, primarily from RAM.

The appliance is controlled over wired Ethernet using OSC, initially from a
monome norns. Audio is carried by the DIGI9652 over up to three ADAT banks.

## Hardware target

- Dell OptiPlex 7010
- Intel Core i7-3770S
- 16 GB RAM
- SSD only
- RME DIGI9652, driven by Linux `snd-rme9652`
- NVIDIA GT 730 removed
- miniDSP MCHStreamer and Audient iD44 remain external alternatives, not
  dependencies of the appliance

## Storage and boot model

- EFI/GRUB boot partition
- writable Debian development and rescue system
- shared data partition
- immutable Buildroot slot A
- immutable Buildroot slot B

The exact partition table and deployment commands will be written only after
the installed SSD and firmware boot mode have been inspected. Debian remains
the default boot target until an appliance image passes hardware, audio, and
recovery testing.

## Initial audio targets

- 48 kHz
- begin validation at a 128-sample buffer
- test 64 samples only after the baseline is stable
- build both `scsynth` and `supernova` initially
- no desktop, Qt, PipeWire, PulseAudio, Bluetooth, or Wi-Fi in the appliance
- PREEMPT_RT evaluated using measurements, not assumed to improve DSP throughput

## Repository layout

- `containers/` — pinned build environments; Buildroot is the release factory
- `board/dell-optiplex-7010/` — board configuration and root filesystem overlay
- `package/supercollider-headless/` — Buildroot package integration
- `configs/` — reproducible Buildroot defconfigs
- `supercollider/` — startup code, SynthDefs, tests, and examples
- `scripts/` — build, deployment, hardware, audio, and latency tooling
- `docs/` — architecture, storage, routing, deployment, and measurements

Buildroot itself is not vendored. A supported release and its Docker builder
will be pinned after the host baseline is captured and the SuperCollider
dependency set is validated. Docker is a Debian build-time facility only; the
appliance image contains no Docker daemon.

## Safety rules

- Never overwrite the running or known-good appliance slot.
- Never repartition or update GRUB without displaying and validating exact
  device identifiers first.
- Use filesystem UUIDs in persistent boot configuration.
- Keep generated images and downloaded source archives out of Git.
- Do not confuse the original DIGI9652 with the later HDSP 9652:
  this project requires `snd-rme9652`, not `snd-hdsp`.
- Record measurements before and after every real-time tuning change.

## First hardware session

After Debian is installed, run the non-mutating baseline collector:

```sh
sudo ./scripts/collect-hardware-baseline
```

Review and redact its output before committing it. Then verify the RME card,
ADAT clocking, and multichannel playback before changing partitions or building
the appliance.
