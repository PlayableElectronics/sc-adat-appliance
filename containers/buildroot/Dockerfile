FROM debian:13-slim@sha256:abc9cb88a5587630d7f915f47b23b0668fe250fbfc6457aa4d52b534c1bbf73f

ARG DEBIAN_FRONTEND=noninteractive
ARG BUILDROOT_VERSION=2025.02.9
ARG BUILDROOT_SHA256=7e83c4f2527041df69a214594c8301498a0a2db0f04ac82bf09dac120b71f02b

RUN apt-get update && apt-get install --no-install-recommends -y \
    bc build-essential bzip2 cpio file findutils flex git libelf-dev libncurses-dev \
    libssl-dev make rsync unzip wget xz-utils ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && wget -q https://buildroot.org/downloads/buildroot-${BUILDROOT_VERSION}.tar.xz \
    && echo "${BUILDROOT_SHA256}  buildroot-${BUILDROOT_VERSION}.tar.xz" | sha256sum -c - \
    && tar -xJf buildroot-${BUILDROOT_VERSION}.tar.xz -C /opt \
    && ln -s /opt/buildroot-${BUILDROOT_VERSION} /opt/buildroot \
    && rm buildroot-${BUILDROOT_VERSION}.tar.xz

WORKDIR /work
ENTRYPOINT ["/work/scripts/build-native-candidate"]
