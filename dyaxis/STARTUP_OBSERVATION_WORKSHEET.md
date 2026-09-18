# Standalone startup observation worksheet

Purpose: capture existing local behavior before any transmission or hardware
modification. No original Macintosh host is required.

## One video

1. Start recording before power is applied; include the rear panel, both
   displays, all faders and the visible LEDs.
2. Power on from a fully off state and continue until motion/text stops and
   the controller reaches its waiting or error state.
3. Do not connect a host or transmit to either RS-422 port.
4. Repeat once while holding only **M1 and F1 at power-on**, because that exact
   diagnostic combination is embedded in U17 text at ROM address `0x0515`.
   If the controls are not physically identifiable, omit this repeat.

## Details to extract from the video

- Do faders move together, in banks, or sequentially? Record order and timing.
- Record every displayed text string, including transient messages.
- Record final LED pattern and whether any LEDs blink.
- Record final display state: ready, idle, test, checksum, error, or blank.
- Note whether the same sequence occurs on both power cycles.

The preferred handoff is the video file itself; do not type a long diagnostic
log. Derived frame timestamps and transcriptions can be added to the repository
after review.
