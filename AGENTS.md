# Agent instructions

Work toward a reproducible, measured audio appliance.

## Architectural boundaries

- Debian is the writable development, recovery, hardware-inspection and
  deployment host.
- Docker runs on Debian and contains reproducible build toolchains.
- The authoritative appliance release is built by the pinned Buildroot
  container. It must include the kernel, root filesystem, scsynth/supernova,
  plugins, Dyaxis services and all validated runtime libraries.
- Buildroot slots A and B are immutable releases booted directly by GRUB.
- The appliance runs natively, primarily from RAM, and contains no Docker
  daemon or development toolchain.
- Containers build, test and package artifacts. Host-side deployment code
  validates artifacts and writes only an explicitly selected inactive slot.
- Do not install a compiler or project toolchain directly on Debian when it
  belongs in a project container. Host packages are limited to Docker, Git,
  Codex, GRUB/storage tools, hardware diagnostics and deployment necessities.
- Hardware validation may run a staged native binary on Debian when direct
  access to the DIGI9652, real-time scheduling or USB devices is required.
  That exception does not make Debian the release environment.

## Safety and evidence

- Never repartition, format, write a block device, install a bootloader, or
  change the GRUB default without first showing the exact resolved devices,
  filesystems, UUIDs, active root, slot state and proposed command to the user.
- Never overwrite the running or last-known-good appliance slot.
- The audio card is the original RME DIGI9652. Its Linux driver is
  `snd-rme9652`; do not substitute instructions for the HDSP 9652.
- Do not claim a kernel, package, buffer size, container image or tuning change
  works until it has been built and tested on the target.
- Capture a baseline before tuning and compare one change at a time.
- Stop on the first build or test failure and diagnose it before continuing.
- Keep generated images, downloads, recordings, compiler caches and
  machine-specific reports out of Git unless the user explicitly approves
  them.
- Pin Buildroot, Linux, SuperCollider and container base-image versions only
  after the target baseline and dependency tests justify the choices.
