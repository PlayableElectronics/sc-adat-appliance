# Trackball and candidate host findings

Photos: `photo/trackball/2704.jpg` through `2711.jpg`.

## Trackball PCB

- The PCB is clearly a **Kensington** board, marked **(C) 1991 KENSINGTON**.
- Board marking: **SCE-ADB-S-1.3**; the board is labelled Made in USA.
- Main ASIC marking: **Kensington 2237424 9344KA / ADB 4.0 R1**.
- The board contains two optical wheel sensors, a button switch, discrete
  conditioning parts and an ADB interface ASIC. This is a complete ADB
  peripheral, not a raw quadrature-only trackball.
- The board exposes a connector marked **P2** plus other local headers; the
  exact ADB pin order still needs continuity mapping. Do not guess it from the
  visual cable colours.
- The new close-ups show a four-contact header/breakout marked **P1**, wired
  one-to-one to the four contacts of the neighbouring ADB connector. This is
  the preferred jumper-wire test point: it should expose DATA, PSW, +5 V and
  GND without modifying the trackball PCB.
- On 2026-09-06, an Arduino Uno running `arduino/ADBHostProbe/ADBHostProbe.ino`
  successfully polled the isolated trackball at ADB address 3. Register 3
  returned the stable two-byte response `6C 02`, proving that power, DATA,
  pull-up, pin assignment and ADB timing are all working. Register 0 produced
  no packets while the ball was stationary; movement/button capture is next.
- A 30-second capture is saved at
  `captures/adb-capture-2026-09-06.log`. It contains 42 `D3R0` register-0
  packets, including values such as `FF 80`, `82 80`, `81 81`, `9B 81`, and
  `FF F6`, while the trackball was moved/clicked. This confirms that the
  Kensington trackball is functioning electrically and generating ADB motion/
  button reports. The packet decoder and button-bit assignment remain to be
  documented against controlled single-axis and button tests.

## Candidate Arduino

- `2708.jpg`/`2709.jpg` show an Arduino Mega-compatible board with an
  **ATmega2560**, marked **Mega 2560 R3** on the rear.
- This is a 5 V MCU, so it is suitable for a first ADB host experiment and
  avoids the 3.3 V GPIO hazard of the RPi/RP2040.
- It does not need to generate USB HID for the first test: use its USB serial
  connection to the RPi 400 and stream raw ADB frames. HID/OSC/MIDI translation
  can run on the RPi.

## Keyboard sharing hypothesis

ADB is a multidrop bus: a keyboard and trackball can share one DATA line and
are distinguished by ADB addresses/handler IDs. The photos establish that the
trackball PCB itself is an ADB device, but they do not yet prove whether the
Dyaxis wiring presents both devices on one physical line or routes them through
separate controller ports. The correct next test is continuity mapping from the
trackball P2 harness to the console's ADB connector(s), with power removed.

This hypothesis is now confirmed in hardware: the keyboard and trackball work
simultaneously on the shared bus. Current bridge state and exact wiring are in
`ADB_BRIDGE_STATUS.md`.

## Safe next step

1. Photograph P2 and its mating cable with pin numbers/colours visible.
2. Use continuity mode to identify P2 ground and +5 V, then the DATA wire by
   tracing it to the Kensington ASIC.
3. Confirm the board's current draw from a current-limited 5 V supply.
4. Connect the Mega only to the isolated trackball PCB: common GND, regulated
   +5 V, and DATA through a 1 kΩ pull-up/open-drain interface. Leave PSW
   disconnected.
5. Run an ADB host capture sketch and send raw transactions over Mega USB
   serial to the RPi.
