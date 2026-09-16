FROM debian:13-slim@sha256:abc9cb88a5587630d7f915f47b23b0668fe250fbfc6457aa4d52b534c1bbf73f

ARG DEBIAN_FRONTEND=noninteractive

# Keep the package set in the image, not on Debian. The base tag and package
# versions are recorded by the build output; refresh them deliberately.
RUN apt-get update \
    && apt-get install --no-install-recommends -y \
        alsa-utils \
        jack-example-tools \
        jackd2 \
        iproute2 \
        libzita-alsa-pcmi0t64 \
        libzita-resampler1 \
        pciutils \
        procps \
        psmisc \
        supercollider-server \
        supercollider-language \
        gcc \
        libc6-dev \
        util-linux \
    && rm -rf /var/lib/apt/lists/*

COPY containers/sc-development/sc-audio-entrypoint /usr/local/bin/sc-audio-entrypoint
COPY containers/sc-development/sc-audio-status /usr/local/bin/sc-audio-status
COPY board/dell-optiplex-7010/rootfs-overlay/usr/bin/sc-adat-tone-test /usr/bin/sc-adat-tone-test
COPY package/sc-adat-tone-test/sc-adat-tone-osc.c /tmp/sc-adat-tone-osc.c
COPY package/sc-adat-tone-test/sc-adat-osc-loader.c /tmp/sc-adat-osc-loader.c
RUN test "$(sclang -v 2>&1 | sed -n 's/.*sclang[[:space:]]\+\([0-9][0-9.]*\).*/\1/p' | head -1)" = 3.13.0 \
    && gcc -O2 /tmp/sc-adat-tone-osc.c -o /usr/bin/sc-adat-tone-osc \
    && gcc -O2 /tmp/sc-adat-osc-loader.c -o /usr/bin/sc-adat-osc-loader \
    && chmod 0755 /usr/local/bin/sc-audio-entrypoint /usr/local/bin/sc-audio-status /usr/bin/sc-adat-tone-test /usr/bin/sc-adat-tone-osc /usr/bin/sc-adat-osc-loader

ENTRYPOINT ["/usr/local/bin/sc-audio-entrypoint"]
