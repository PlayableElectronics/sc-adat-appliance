# Reverse-engineering plan

## Phase 0 — identify and preserve

1. Photograph the complete surface powered off.
2. Record model, serial, revision and all cable/connector labels.
3. Photograph each board front/back before removing shields or chips.
4. Make a board inventory: board ID, MCU, ROM, logic, connectors, oscillator,
   power devices and visible test points.

## Phase 1 — power and buses

1. With boards disconnected, map continuity and grounds.
2. Identify mains/low-voltage supplies and measure rails with a current-limited
   bench supply where practical.
3. Determine whether the three boards share a backplane bus or use point-to-
   point serial links.
4. Look first for ADB electrical levels, RS-422 line drivers, UARTs, and
   multiplexed switch/fader scanning. Do not assume every DB connector is
   RS-422.

## Phase 2 — firmware preservation

1. Read every EPROM twice and compare hashes.
2. Save raw dumps with chip marking, programmer, voltage, date and checksum.
3. If a ROM is socketed, do not erase or reprogram it.
4. Identify CPU family from package/marking before choosing a disassembler.
5. Search dumps for ASCII labels, ADB strings, baud rates, device IDs and
   lookup tables.

## Phase 3 — passive protocol capture

1. Capture boot traffic with the original host/controller arrangement if the
   unit can still be operated safely.
2. Trigger on one button, encoder, fader, jog movement and LED/display event
   at a time.
3. Capture both directions: controller-to-host input and host-to-controller
   feedback.
4. Correlate event bytes with physical controls and determine framing,
   checksums, addressing, repeat rate and idle traffic.

## Phase 4 — replacement interface

Build a removable adapter, not a permanent board modification. Suggested
first target:

- USB MIDI + USB serial debug;
- OSC over Ethernet/Wi-Fi through a small companion computer;
- MIDI CC/NRPN for faders and encoders;
- MMC or Mackie/HUI-compatible transport mapping;
- HID keyboard/mouse for buttons and trackball if useful;
- configurable LED/display feedback later.

## Safety and evidence rules

- Never write to an original EPROM.
- Use a current-limited supply during first power tests.
- Use differential probes or proper RS-422 receivers for balanced serial lines.
- Keep a raw, immutable dump and a lab notebook entry for every experiment.
- Preserve original harnesses and make adapter cables with keyed labels.
