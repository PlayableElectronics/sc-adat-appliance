#!/bin/sh
# Run Dronage Terminal (ALSA-only) through the Patchbox JACK server.
set -eu

RATE=${DRONAGE_RATE:-48000}
PERIOD=${DRONAGE_PERIOD:-1024}
NAME=${DRONAGE_JACK_NAME:-Dronage-ALSA}
if [ -n "${DRONAGE_APP:-}" ]; then
  APP=$DRONAGE_APP
else
  APP=$(find /home/patch -type f -name 'dronage-terminal-linux-arm64' -perm -u+x 2>/dev/null | sort | tail -1)
fi
CFG=/tmp/dronage-loopback-alsa.conf

if ! command -v jack_lsp >/dev/null 2>&1; then
  echo 'JACK tools are not installed (jack_lsp missing).' >&2
  exit 1
fi
if ! command -v alsa_in >/dev/null 2>&1; then
  echo 'alsa_in is not installed; install jackd2/jack-tools first.' >&2
  exit 1
fi
if [ ! -x "$APP" ]; then
  echo "Dronage binary not found or not executable: $APP" >&2
  exit 1
fi

sudo modprobe snd-aloop || true
cat >"$CFG" <<'EOF'
pcm.!default {
  type plug
  slave.pcm "plughw:CARD=Loopback,DEV=0"
}
ctl.!default {
  type hw
  card Loopback
}
EOF

alsa_in -j "$NAME" -d hw:Loopback,1 -r "$RATE" -p "$PERIOD" -n 2 \
  > /tmp/dronage-jack-alsa.log 2>&1 &
BRIDGE_PID=$!
cleanup() { kill "$BRIDGE_PID" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

sleep 1
jack_connect "$NAME:capture_1" system:playback_1 2>/dev/null || true
jack_connect "$NAME:capture_2" system:playback_2 2>/dev/null || true

printf 'Launching %s at %s\\n' "$APP" "$(date)" >> /tmp/dronage-jack-alsa.log
set +e
ALSA_CONFIG_PATH="$CFG" ALSA_CARD=Loopback ALSA_PCM_CARD=Loopback ALSA_PCM_DEVICE=0 \
  "$APP" --buffer-size "$PERIOD" "$@" \
  >> /tmp/dronage-jack-alsa.log 2>&1
RC=$?
printf 'Dronage exited with status %s at %s\\n' "$RC" "$(date)" >> /tmp/dronage-jack-alsa.log
exit "$RC"
