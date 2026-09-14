# Photo findings — 2026-09-06

The photo set currently includes `photo/2665.jpg` through `photo/2676.jpg` and
new close-ups `photo/2684.jpg` through `photo/2699.jpg`.

`photo/2677.jpg` is a close-up of the FPGA.

## High-confidence identifications

- `2676.jpg` clearly identifies the main board as **DYAXIS II CONSOLE — EDIT
  PANEL CPU BOARD**, assembly **41.005.430.01**, dated **AUG. 1993**, made in
  the USA by Studer Editech.
- The main CPU is a Philips **P80C552-5**, marked `16WP`, with Philips date/
  lot markings. This is an 8051-family microcontroller with integrated
  peripherals, making it a very plausible control scanner/host interface.
- The CPU board has a socketed EPROM labelled approximately
  `41.005.434.21 / 13 / EDIT? / SEC 1994` (the label needs a sharper,
  straight-on photograph before transcription is final).
- The CPU board has a **12.000 MHz** oscillator and a 26-pin connector J2 plus
  a larger keyed connector J1. These are immediate targets for continuity
  mapping and passive logic capture.
- The new close-ups confirm that multiple boards share the P80C552 CPU family
  and each carries socketed program EPROM firmware. This points to
  distributed, firmware-defined subsystems rather than passive satellite
  cards.
- The owner confirms an FPGA on the main board. Its exact vendor/device marking
  is not yet legible and is now a priority for one square-on close-up.
- `2677.jpg` resolves that device: it is a Xilinx **XC3030**-family FPGA,
  apparently marked `XC3030TM-70 PC68C` (the suffix should be transcribed from
  a perfectly flat image before treating every character as certain). The
  package is a 68-pin PLCC. Additional visible codes include `A19513A` and
  `BYH9344`, likely manufacturing/date/lot codes.
- `2671.jpg` shows another Philips **P80C552-5** on a separate board, so at
  least two of the three reported boards appear to have their own 8051-family
  CPU rather than being passive I/O cards.
- `2694.jpg` identifies a second board as **UPTOWN AUTOMATION — CONTROLLER
  FADER**, assembly/revision **935 Rev B**, made in the USA. It visibly carries
  another P80C552-5, fader connectors, driver circuitry and a socketed EPROM.
- `2667.jpg` shows a Zilog **Z85230**-family device (marking appears
  `Z85230...ESC`, date code 9319) and a 3.672 MHz oscillator. This is a major
  lead for serial communications; confirm the exact suffix and which board it
  belongs to.
- `2673.jpg` appears to show an Intel **P80C31**-family or related 8051 ROMless
  controller/processor, but the photograph is not sharp enough for a final
  identification. Retake this chip square-on.
- `2674.jpg` shows a socketed **Xicor** device marked approximately
  `22-00958-000 / CS?1455`; it may be a programmable logic or nonvolatile
  configuration device. Retake the label perpendicular to the package.

## Other observations

- The boards use many 74xx/CMOS logic ICs, resistor networks, DIP switches,
  ribbon-cable headers and socketed firmware. This is good news for probing and
  repair: the design is comparatively observable and not an opaque modern SoC.
- `2665.jpg` shows a dense stack of boards connected by multiple ribbon cables.
  Cable destinations and board order need a labelled overview photo before
  any disconnection.
- `2669.jpg` has Studer Editech/automatic-controller markings and should be
  photographed again with the entire board reference visible.
- `2675.jpg` shows the internal power-supply area. Do not probe or modify it
  until the mains/low-voltage boundary and ground reference are documented.

## Immediate implications

1. Preserve and dump the socketed EPROMs before any protocol work.
2. Treat every P80C552 board as an independent intelligent node until the
   inter-board bus is mapped.
3. Investigate the Z85230 section as a possible dual-channel serial link,
   without assuming it is RS-485 until the line drivers are identified.
4. Use the 12 MHz and 3.672 MHz clocks as capture/disassembly timing clues.
5. Photograph the connector pin fields and trace the CPU-board J1/J2 signals
   to the ADB/RS-485 connectors.
6. Photograph the main-board FPGA square-on and record its complete marking,
   package and any nearby configuration PROM or clock.

## FPGA-area close-ups

- `photo/fpga/2700.jpg` and `2702.jpg` show two nearby socketed programmed ROMs
  with Studer assembly labels beginning **41.005.415.71** and **41.005.416.70**.
- `photo/fpga/2703.jpg` clearly shows a **PALC22V10L-25PC**, marking
  **9353 000020**. This is programmable logic, not an EPROM, and may implement
  address decoding or FPGA/CPU glue logic.
- These parts form a likely FPGA configuration/boot cluster, but the exact
  ROM-to-FPGA relationship remains to be established by tracing and capture.
