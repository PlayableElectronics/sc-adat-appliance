# Build containers

This directory will hold the reproducible, headless toolchain definitions used
on the writable Debian host.

The first implementation target is `buildroot/`, which must produce the
complete native SC-ADAT appliance release. Additional lab toolchains may be
added independently without becoming runtime dependencies.

See [the containerized build architecture](../docs/container-build.md).

Do not add placeholder Dockerfiles with untested versions. Capture the Dell
hardware baseline, validate the required SuperCollider dependency set, then pin
and implement each image deliberately.
