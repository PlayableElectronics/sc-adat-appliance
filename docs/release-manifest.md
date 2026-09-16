# Appliance release manifest

Each release must carry a manifest beside its kernel and root filesystem:

```text
release_id=
git_commit=
builder_image_digest=
buildroot_version=
supercollider_version=
linux_version=
kernel_config_sha256=
rootfs_sha256=
kernel_sha256=
build_timestamp_utc=
target=dell-optiplex-7010
rootfs_mode=
rootfs_artifact_sha256=
grub_entry_sha256=
audio_driver=snd-rme9652
```

Build provenance does not prove hardware validation. Promotion to known-good
also requires a matching test record from the target.
