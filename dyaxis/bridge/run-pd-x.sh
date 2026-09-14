#!/bin/sh
# Launch Pure Data in a minimal local X session on Patchbox.
log=/tmp/pd-x.log
: > "$log"
printf "pd-x invoked at %s\\n" "$(date)" >> "$log"
exec startx /usr/local/bin/pd-x-client -- :0
