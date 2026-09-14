# Dyaxis ADB bridge — working state (2026-09-06)

This is the resume point for the Studer Dyaxis keyboard/trackball bridge.

## Working hardware

- Dedicated Raspberry Pi 400: SSH alias `patchbox`, user `patch`, LAN address
  `192.168.1.45`.
- Classic Arduino Nano-compatible ATmega328P/CH340 on Patchbox as
  `/dev/ttyUSB0` (replaced the original Uno on 2026-09-06).
- Uno D2 is the open-collector ADB DATA connection.
- External 4.7 kΩ pull-up from DATA to +5 V.
- P1 lower-left = GND, lower-right = +5 V, upper-right = DATA; upper-left PSW
  is unused.
- Keyboard and Kensington trackball share the same ADB DATA, +5 V and GND.
- ADB keyboard is address 2, handler ID `0x02`; trackball is address 3,
  handler ID `0x02`.

## Installed software

- Uno source: `arduino/ADBHostProbe/ADBHostProbe.ino`.
- Pi translator: `bridge/adb_mouse_bridge.py`, installed as
  `/usr/local/sbin/dyaxis-adb-mouse.py`.
- systemd unit: `bridge/dyaxis-adb-mouse.service`, installed and enabled as
  `dyaxis-adb-mouse.service`.
- Pi dependency: Debian `python3-evdev`.
- Virtual input devices:
  - `Studer Dyaxis Kensington ADB Trackball`
  - `Studer Dyaxis ADB Keyboard`
- Useful check: `ssh patchbox 'systemctl status dyaxis-adb-mouse'`.

## Protocol and behavior already fixed

- Uno polls keyboard register 0 at address 2 and mouse register 0 at address 3.
- Poll delay is 10 ms. Five ms was fast but is below the reliable range for
  some old keyboards; 80 ms caused obvious lag.
- Mouse packets use active-low buttons and signed seven-bit relative axes.
- Keyboard packets contain up to two scan codes; high bit means release.
- Linux key repeat is synthesized with EV_KEY value 2, 500 ms delay and 50 ms
  period. Only the newest printable key repeats.
- A five-second watchdog emits a release if an ADB release packet is lost.
- ADB Caps Lock alternates make/break edges. Either physical edge is converted
  to a complete Linux Caps tap.
- Controller startup policy is Caps Lock off and Num Lock on.
- Num Lock on makes the Apple keypad produce digits; Clear maps to Num Lock.
- ADB Power key maps to Linux `KEY_POWER` and currently powers off the Pi.
- Correct ADB LISTEN transaction: command stop, about 200 µs Tlt, data start
  bit, continuous data bytes, then one final stop bit. The earlier implementation
  omitted the data start bit and inserted a stop between bytes, so LED commands
  were ignored.
- Startup sends lock state once immediately and again after the first valid
  keyboard register-3 response, avoiding the ADB-reset race.

## Last observed state

- Typing, trackball motion, buttons, low latency, key repeat and numpad work.
- Corrected LISTEN firmware was successfully flashed (`3522 bytes`, avrdude
  return code 0), and the service was active afterward.
- Caps initialization was much better after the LISTEN fix. On that test, the
  lamp initially remained on once, but cycling Caps off/on brought behavior
  into sync. A status-confirmed startup resend was subsequently deployed and
  still needs validation across a full Pi/Uno cold boot.

## Recommended next checks

1. Cold-boot Patchbox and confirm Caps starts logically off with its lamp off,
   Num Lock starts on, and no manual Caps cycle is required.
2. If Caps still starts lit, capture keyboard register 2 after reset and use it
   to confirm the exact LED bit polarity/state rather than adding another
   blind inversion.
3. Test every keypad, modifier, navigation and function key against `evtest`;
   add any missing ADB scan-code mappings.
4. The Uno-to-Nano migration is complete. Preserve the requirement for a
   **classic Arduino Nano, ATmega328P, 5 V, 16 MHz**; D2 and the existing
   firmware/wiring are compatible. Do not substitute a 3.3 V Nano or Nano
   Every without adapting electrical levels and direct AVR port-register code.

## Flash procedure that works

The Pi service must fully release `/dev/ttyUSB0` before flashing:

```sh
ssh patchbox 'sudo systemctl stop dyaxis-adb-mouse'
# build with arduino-builder for arduino:avr:uno, then:
ssh patchbox 'avrdude -V -patmega328p -carduino -P /dev/ttyUSB0 -b115200 \
  -U flash:w:/home/patch/adb-build/ADBHostProbe.ino.hex:i'
ssh patchbox 'sudo systemctl start dyaxis-adb-mouse'
```

Use `-V`: verification repeatedly lost bootloader sync on the streaming CH340
connection even when the write completed. Always restore the service after a
failed flash attempt and kill any stale `avrdude` process before retrying.

The installed Nano clone uses the newer **115200-baud** bootloader. A 57600-baud
old-Nano attempt timed out; the 115200-baud flash wrote all 3522 bytes and
returned success. A post-flash capture received keyboard `K2R3 ... 02`, and the
bridge service was restored active.
