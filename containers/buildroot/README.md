# Buildroot builder

This container is the authoritative factory for SC-ADAT appliance releases.

It will provide the host dependencies required by a pinned Buildroot version,
mount the repository at `/work`, retain downloads/compiler state in
`/cache`, and emit only versioned bundles beneath `/artifacts`.

The image does not run scsynth as the production appliance. It builds the
kernel and target filesystem that GRUB later boots natively.

Implementation is intentionally deferred until the Dell baseline establishes:

- amd64/firmware boot mode;
- working `snd-rme9652` configuration;
- selected Buildroot and Linux versions;
- validated headless SuperCollider dependencies;
- chosen initramfs/SquashFS RAM-root design.
