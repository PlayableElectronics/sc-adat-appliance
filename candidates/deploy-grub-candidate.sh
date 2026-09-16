#!/bin/sh
set -eu

echo 'PREPARED DEPLOYMENT ONLY: this script intentionally refuses to mutate GRUB.' >&2
echo 'Review docs/native-candidate-deployment.md, then obtain explicit approval' >&2
echo 'before replacing this gate with the approved host-side copy/grub steps.' >&2
exit 2
