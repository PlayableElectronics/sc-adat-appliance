# Studer Dyaxis controller conversion

This folder is the working dossier for preserving the Dyaxis control surface
and adapting it as a modern MIDI/OSC/HID controller for the SuperCollider ADAT
appliance. Original hardware, firmware, ROMs, programmable logic, connectors
and harnesses are preservation material.

## Confirmed from the owner's unit

The surface powers up and operates when the original computer-side software
responds; otherwise it waits for the host. It contains a VFD, knobs/encoders,
buttons, motorised faders, trackball, keyboard and multiple intelligent boards.
Rear-panel photo 2865 confirms two ports explicitly labelled `(RS422) SERIAL
1` and `(RS422) SERIAL 2`, two ADB ports, a `METER POWER +5V (2A MAX.)`
connector and a separate `NETWORK` connector. Photos 2867 and 2868 identify
the connector PCB as the Studer Editech Multi-Desk I/O Panel, assembly
41.005.440.20. The NETWORK protocol and all non-ADB pinouts remain unknown.

At least two boards use Philips P80C552-5 8051-family processors. The main edit
panel CPU board also contains a Z85230-family dual serial controller and an
XC3030-family FPGA. See `KNOWN_FACTS.md` and the photo findings for evidence
and confidence levels.

## Working ADB subsystem

The ADB keyboard and Kensington trackball already work through the current
classic Arduino Nano-compatible ATmega328P/CH340 bridge running at 5 V and
16 MHz. The bridge exposes an event stream through USB serial; the Linux
translator creates standard keyboard and mouse devices with `uinput`.

Keep this subsystem intact and portable. Its next deployment target is the
Debian development system and, later, the read-only Buildroot appliance—not a
specific Raspberry Pi host.

Relevant files:

- `arduino/ADBHostProbe/ADBHostProbe.ino`
- `bridge/adb_mouse_bridge.py`
- `bridge/dyaxis-adb-mouse.service`
- `ADB_BRIDGE_STATUS.md`
- `ADB_BRINGUP.md`

## Conversion target

1. Preserve the original controller electronics and connectors.
2. Preserve and analyse every socketed ROM before protocol experiments.
3. Identify the roles and links of the intelligent boards.
4. Identify the NETWORK electrical interface and trace it to the controller
   electronics without assuming it is Ethernet.
5. Passively inspect both labelled RS-422 interfaces using proper differential
   receivers.
6. Determine whether the original host uses NETWORK or RS-422, then emulate
   that protocol from Linux.
7. Translate the complete surface bidirectionally to OSC, with optional
   MIDI/HID compatibility.
8. Map the eight faders as three banks across the 24 ADAT mixer channels and
   use the remaining controls for routing, buses, monitoring, looping and
   effects.

The ADB USB-serial bridge is a proven independent subsystem. Main-surface
RS-422 host emulation is a separate, unfinished layer.

See `REVERSE_ENGINEERING_PLAN.md` for the staged procedure and
`SOURCES.md` for the research trail.
