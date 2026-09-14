# Work to do before the ROM/PAL programmer arrives

## Safe documentation

- Photograph every chip orientation, label and socket position.
- Make a board map: board name, assembly/revision, CPU, ROMs, PALs, FPGA,
  clocks and connectors.
- Label both ends of every ribbon cable before disconnecting anything.
- Record which boards are connected to ADB, RS-422, NETWORK, VFD, faders,
  keyboard and trackball.
- Keep the original photos and notes immutable; work from copies.

## Identify devices without removing them

- Count pins and note package type for every ROM and PAL.
- Record visible manufacturer, family and speed markings around the label
  edges. Do not peel more labels unless necessary and photographed first.
- Download datasheets and draw provisional pin maps for the ROMs, PALC22V10,
  XC3030 and P80C552.
- Locate the FPGA configuration pins (DIN/DATA, CCLK, DONE, PROG/RESET,
  mode pins) from the XC3030 package pinout and mark their board vias.

## Continuity mapping, powered off

- With power removed, map ROM address/data/control pins to the P80C552 and
  XC3030 using a multimeter continuity function.
- Identify shared buses and chip-select lines; do not inject signals.
- Find ground and +5 V pins from board planes and connector wiring.
- Identify RS-422 transceiver ICs and trace their differential pairs to SERIAL 1/2.
- Trace the NETWORK connector separately; do not assume Ethernet from its shape.
- Check for termination resistors and selectable bias networks.

## Passive powered measurements

- Measure supply rails at the connector and each board with a current-limited
  supply or the original system operating normally.
- Confirm logic-high voltage before attaching any analyzer.
- Use a high-impedance oscilloscope or logic analyzer only; do not connect a
  programmer, Raspberry Pi GPIO or FPGA pins directly to an unknown bus.
- Capture power-up on the FPGA configuration pins and ROM chip-select/output
  enables if accessible.
- Capture one action at a time: button, encoder, fader, motor movement,
  keyboard key, trackball movement and VFD update.

## Useful records to make now

- A CSV table of connector pin number, wire colour, destination and observed
  idle voltage.
- A signal glossary: `CPU board`, `fader board`, `FPGA board`, `ADB`, `RS422-SERIAL-1`,
  `RS422-SERIAL-2`, `NETWORK`, `VFD`, `MOTOR`, `KEYBOARD`, `TRACKBALL`.
- Logic-analyser files with sample rate, voltage threshold, probe location and
  exact physical action recorded in the filename.
- A power-up video showing the VFD, LEDs and motor-fader behaviour.

## Do not do yet

- Do not remove or rewrite an EPROM/PAL.
- Do not connect the RPi 400 GPIO directly to ADB, RS-422, NETWORK or the ROM bus.
- Do not unplug boards while powered.
- Do not assume the two ROMs are interchangeable or that either one is the
  FPGA bitstream source.
