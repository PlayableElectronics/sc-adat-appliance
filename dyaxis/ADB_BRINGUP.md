# ADB trackball bring-up

## Recommended first topology

```text
Dyaxis trackball PCB
        │ 4-pin ADB harness / mini-DIN breakout
        ▼
5 V ADB host adapter MCU  ── USB CDC/HID ──>  RPi 400
        │
        └── optional logic-analyser tap on DATA
```

Use the MCU for ADB timing and open-drain bus handling. The available Arduino
Mega 2560 R3 is a suitable first host: it is a 5 V ATmega2560 board. Use the RPi 400 for
logging, translation to OSC/MIDI, configuration and later integration with the
rest of the console. Linux's normal ADB driver cannot help unless a real ADB
electrical interface is attached; the Pi has no native ADB port.

## Mini-DIN-4 wiring

Looking into the **female ADB socket on the device**:

| Pin | Function | First test |
|---:|---|---|
| 1 | ADB DATA, bidirectional open-collector | connect to MCU bus through a 5 V-safe open-drain interface |
| 2 | PSW / power-switch signal | leave unconnected for the trackball test |
| 3 | +5 V | regulated 5 V supply; measure current first |
| 4 | GND | common ground |

Do not use an arbitrary S-video cable: some cables bridge pins 1 and 2 and can
damage the device. ADB uses a single 5 V pulled-up data wire; all devices pull
the line low and no device should actively drive it high. The bus is typically
around 10 kbit/s, with 125 kbit/s as a theoretical maximum.

For a first bench harness, use a separate regulated 5 V supply, common ground,
and a 1 kΩ pull-up from DATA to 5 V. Keep the trackball's current below the
ADB device budget. Do not connect the DATA line directly to a Raspberry Pi or
RP2040 GPIO: those pins are not 5 V tolerant. A 5 V ATmega32U4 board, or a
proper bidirectional open-drain level shifter, is a safer first host.

The photographed Kensington board is marked `SCE-ADB-S-1.3` and uses a
`2237424 ... ADB 4.0` controller, so it should be tested as a complete ADB
peripheral. First map its P2 connector by continuity; do not assume the
connector's visible wire order is the standard mini-DIN order.

## Software starting points

1. **TMK ADB-USB converter** — the most practical first test. It supports ADB
   keyboards, mice and several trackball families and exposes USB HID. Start
   with its `converter/adb_usb` implementation and use its raw/debug output if
   the Dyaxis trackball reports an unknown handler ID.
2. **Apple ADB Manager documentation** — use for command framing, reset,
   enumeration, Talk/Listen/Flush and service requests.
3. **Linux `adbhid.c`** — use as a decoder reference for mouse/trackball data
   once the MCU produces USB or serial events.

The normal mouse/trackball address is 3; the keyboard address is 2. A host
starts with reset/enumeration, then polls Talk Register 0. Do not hard-code
the device type before reading its handler ID and register responses.

## Bring-up sequence

1. Power the isolated trackball PCB from regulated 5 V with the MCU detached;
   confirm no unexpected heating and measure current.
2. Connect GND and DATA to the MCU host, with the host's pull-up and level
   protection in place. Leave PSW disconnected.
3. Capture the idle line, reset response and first Talk transactions.
4. Run enumeration and record the device address, handler ID and register
   lengths.
5. Poll Register 0 while moving the ball and pressing each button; save raw
   frames before decoding.
6. Only after raw capture is stable, emit USB HID mouse events and forward
   normalized events to the RPi over USB serial.

## References

- [Microchip AN591 ADB application note](https://ww1.microchip.com/downloads/en/AppNotes/00591b.pdf)
- [TMK ADB protocol and converter notes](https://github.com/tmk/tmk_keyboard/wiki/Apple-Desktop-Bus)
- [TMK ADB USB converter source](https://github.com/tmk/tmk_keyboard/tree/master/converter/adb_usb)
- [Apple ADB Manager PDF](https://developer.apple.com/library/archive/documentation/mac/pdf/Devices/ADB_Manager.pdf)
- [Linux ADB HID decoder](https://github.com/torvalds/linux/blob/master/drivers/macintosh/adbhid.c)
