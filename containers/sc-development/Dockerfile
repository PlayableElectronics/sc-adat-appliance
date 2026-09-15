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
        util-linux \
    && rm -rf /var/lib/apt/lists/*

COPY sc-audio-entrypoint /usr/local/bin/sc-audio-entrypoint
COPY sc-audio-status /usr/local/bin/sc-audio-status
RUN chmod 0755 /usr/local/bin/sc-audio-entrypoint /usr/local/bin/sc-audio-status

ENTRYPOINT ["/usr/local/bin/sc-audio-entrypoint"]
