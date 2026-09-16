#!/bin/sh
set -eu

TARGET_DIR=$1
FACTORY="$TARGET_DIR/usr/share/sc-adat/factory"
test -d "$FACTORY"

# Package installation intentionally leaves TARGET_DIR writable. This hook
# runs during Buildroot's fakeroot finalization and makes the shipped factory
# payload immutable without breaking incremental unprivileged builds.
chown -R 0:0 "$FACTORY"
find "$FACTORY" -type d -exec chmod 0555 {} +
find "$FACTORY" -type f -exec chmod 0444 {} +
chmod 0555 "$FACTORY/scripts/payload-consumer"
