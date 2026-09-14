# Dyaxis ADB USB-serial input bridge

This bridge turns the Dyaxis ADB keyboard and Kensington trackball into normal
Linux input devices. The current bridge is a classic Arduino Nano-compatible
ATmega328P/CH340 board running at 5 V and 16 MHz. It polls the shared ADB bus
and emits packets through USB serial. The Python translator reads that stream
and creates Linux `uinput` keyboard and mouse devices.

Do not substitute a 3.3 V Nano or Nano Every without adapting the electrical
interface and the firmware's AVR-specific assumptions.

This subsystem is independent of the unfinished Dyaxis main-surface/RS-422
protocol work and must be preserved for the Debian development system and the
eventual Buildroot appliance.

## Components

- Arduino Nano firmware: `../arduino/ADBHostProbe/ADBHostProbe.ino`
- Linux translator: `adb_mouse_bridge.py`
- systemd unit: `dyaxis-adb-mouse.service`
- Default serial device: `/dev/ttyUSB0`
- Python dependencies: `pyserial` and `evdev`
- Kernel facility: `uinput`

The translator creates:

```text
Studer Dyaxis Kensington ADB Trackball
Studer Dyaxis ADB Keyboard
```

The systemd service runs as root so it can open `/dev/uinput`, and restarts
when the serial bridge is temporarily unavailable.

Useful checks:

```sh
systemctl status dyaxis-adb-mouse
journalctl -u dyaxis-adb-mouse -f
```

The Nano polls conventional ADB keyboard address 2 and mouse/trackball address
3. Keyboard register-0 events become Linux key events. Linux lock state is sent
back to the keyboard LEDs. Trackball packets use active-low button bits and
signed seven-bit relative axes.

For tested wiring, protocol details, flashing procedure and the historical
Patchbox deployment state, see `../ADB_BRIDGE_STATUS.md`.
