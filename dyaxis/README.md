# Studer Dyaxis controller conversion

This folder is the working dossier for converting the Dyaxis control surface
into a useful modern MIDI/OSC/HID controller. The original hardware and ROMs
must be treated as preservation material: photograph, label and dump before
modifying or desoldering anything.

## Confirmed from the owner's unit

The surface powers up and functions, but waits for the original computer
software to answer. It has ADB ports, two RS-485 connections, a VFD, knobs,
buttons, motorised sliders, a trackball and a keyboard. The owner reports three
microcontroller boards. An RPi 400 is available as a dedicated lab computer.

This makes a staged protocol bridge realistic: the original electronics can be
kept intact while an RPi/MCU/FPGA subsystem emulates the host and translates
events to USB MIDI, OSC and HID.

## Working hypothesis

The surface is a Dyaxis II / MultiDesk-family controller rather than an audio
processor. Period descriptions identify a dedicated edit controller with a
transport section, scrub/shuttle wheel, edit buttons, a mixer panel, and a
computer keyboard/trackball interface. A 1994 description reports eight
faders arranged as two banks of four, four assignable knobs/shaft encoders,
fourteen soft switches, transport controls, and a standard Kensington
trackball connected through ADB. The QWERTY keyboard is also described as a
standard ADB device connected to the Macintosh. These details are strong
leads, but the exact unit variant still needs confirmation from photographs
and PCB markings.

## Conversion target

The safest architecture is a reversible inline replacement:

1. Preserve the original controller electronics and connectors.
2. Identify which board owns each input/output group.
3. Add a new low-voltage controller (RP2040, STM32, FPGA or similar) on an
   adapter harness, initially listening passively; use the RPi 400 for host
   emulation, logging, configuration and OSC/network services.
4. Translate controls to MIDI 2.0/1.0, OSC and optional USB HID.
5. Add a configuration layer for DAW transport, faders, encoders, scrub,
   keyboard shortcuts, mouse/trackball and custom OSC destinations.

Do not connect an unknown board to a modern USB or MIDI interface until power
rails and signal levels are measured.

## Immediate evidence needed from the owner

- Front, rear, top and every PCB, photographed square-on with a ruler.
- Exact model/serial/part numbers and all connector labels.
- Both sides of every board, including silk-screen reference designators.
- Close-ups of every microcontroller, ROM/EPROM, PAL/GAL, UART, oscillator,
  connector driver and power regulator.
- Cable photos before disconnecting anything; mark every cable and pin 1.
- EPROM dumps with chip labels, device type, read voltage and programmer used.
- Resistance-to-ground and powered rail measurements before probing signals.
- Logic-analyser captures during power-up and while pressing one control at a
  time, with the original controller connected if possible.

See `REVERSE_ENGINEERING_PLAN.md` for the staged procedure and
`SOURCES.md` for the research trail.

For the first practical subsystem test, see `ADB_BRINGUP.md`. The recommended
split is a 5 V-safe MCU as the ADB host and the RPi 400 as the logger/translator;
do not connect ADB DATA directly to Pi GPIO.
