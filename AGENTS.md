# Agent instructions

Work toward a reproducible, measured audio appliance.

- Preserve Debian as the writable development and recovery system.
- Treat Buildroot slots A and B as immutable releases.
- Never repartition, format, write a block device, install a bootloader, or change
  the GRUB default without first showing the exact resolved devices, filesystems,
  UUIDs, active root, and proposed command to the user.
- Never overwrite the running or last-known-good appliance slot.
- The audio card is the original RME DIGI9652. Its Linux driver is
  `snd-rme9652`; do not substitute instructions for the HDSP 9652.
- Do not claim a kernel, package, buffer size, or tuning change works until it
  has been built and tested on the target.
- Capture a baseline before tuning and compare one change at a time.
- Stop on the first build or test failure and diagnose it before continuing.
- Keep generated images, downloads, recordings, and machine-specific reports
  out of Git unless the user explicitly approves them.
