#!/bin/sh
log=/tmp/pd-x.log
printf "pd-x client started at %s\\n" "$(date)" >> "$log"
xsetroot -cursor_name left_ptr
# Minimal floating window manager for Pd subwindows and dialogs.
openbox --sm-disable >>"$log" 2>&1 &
wm_pid=$!
trap 'kill "$wm_pid" 2>/dev/null || true' EXIT
exec /usr/bin/pd -jack -stderr >>"$log" 2>&1
