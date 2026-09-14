# Dyaxis ADB input bridge

This bridge turns the Kensington ADB trackball and keyboard connected to the
Uno into normal Linux input devices on the dedicated `patchbox` Raspberry Pi.

## Installed service

The service is installed and enabled as:

```text
dyaxis-adb-mouse.service
```

It reads the Uno's `ADBHostProbe` stream on `/dev/ttyUSB0` and creates these
uinput devices:

```text
Studer Dyaxis Kensington ADB Trackball
Studer Dyaxis ADB Keyboard
```

It runs as root
so it can open `/dev/uinput` on the stock Raspberry Pi OS image, and systemd
restarts it if the USB serial adapter is unplugged or reset.

Useful commands on `patchbox`:

```sh
systemctl status dyaxis-adb-mouse
journalctl -u dyaxis-adb-mouse -f
```

The Uno polls the conventional ADB mouse address 3 and keyboard address 2.
Keyboard register-0 events are decoded into Linux key events; Caps Lock,
Num Lock, and Scroll Lock state is taken from Linux LED output events and sent
back to keyboard register 2. On service startup the bridge seeds those LEDs
from the Pi's existing input LED state, so a restart does not invent a new
Caps Lock state. The dedicated controller startup policy forces Caps Lock off
and Num Lock on, making the Apple numeric keypad produce digits immediately.
The mouse remains a separate device, so keyboard and trackball can share the
same ADB bus without changing the mouse path.

The packet interpretation follows the Linux ADB HID driver: button bits are
active-low, and the two seven-bit signed values are the X/Y relative motion.

For the complete tested state, wiring, flash procedure, resolved bugs and next
checks, see `../ADB_BRIDGE_STATUS.md`.
