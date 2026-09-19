#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
IMAGE=${U17_UCSIM_IMAGE:-sc-adat-u17-ucsim:sdcc-4.5.0-ucsim-0.8.15}

docker build --quiet -f "$ROOT/dyaxis/analysis/ucsim/Dockerfile" -t "$IMAGE" "$ROOT/dyaxis/analysis/ucsim" >/dev/null
# The runner writes only an explicitly requested report/trace path. Firmware
# inputs remain read-only by convention; do not pass a firmware output path.
exec docker run --rm -v "$ROOT:/work" "$IMAGE" "$@"
