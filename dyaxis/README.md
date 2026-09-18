# Studer Dyaxis controller conversion

This folder is the working dossier for preserving the Dyaxis control surface
and adapting it as a modern MIDI/OSC/HID controller for the SuperCollider ADAT
appliance. Original hardware, firmware, ROMs, programmable logic, connectors
and harnesses are preservation material.

## Confirmed from the owner's unit

The surface demonstrates meaningful standalone operation with no original
Macintosh host connected: motorised faders move, LEDs light, and its displays
show text. It contains a VFD, knobs/encoders,
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

## Public firmware archive

The verified U17 EPROM is deliberately published for historical preservation,
repair and interoperability:

- `firmware/README.md` — provenance, preservation notice and verification
  instructions;
- `firmware/SHA256SUMS` — checksum manifest;
- `firmware/original/41.005.415.Z1-U17-V1.06-AM27C256.bin` — the Studer-Editech
  U17 MultiDesk Boot ROM;
- `firmware/original/490-0270-MI-V2.7-M27C128.bin` — the Uptown Automation U7
  controller/fader-board firmware.
- `firmware/original/41.005.431.11-U3-EDIT-V1.1-AM27C256.bin` — the Studer
  Dyaxis II Console Edit Panel U3 firmware from assembly 41.005.430.01.
- `analysis/generated/u17/` — reproducible disasm51 reachable disassembly,
  P80C552 vector/SFR cross-references, call graph and analysis metrics for U17.

The image is associated with the P80C552 controller board and rear RS-422
interfaces. Local intermediate reads remain under ignored `.local/` paths;
derived analysis is kept separate from the untouched original image.

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

The U17-specific reverse-engineering report is
`analysis/RS422_U17_REVERSE_ENGINEERING.md`. It distinguishes verified
instruction-boundary findings from protocol hypotheses and defines the safe
receive-only capture gate before any connector is probed.
The FPGA and external-address reassessment is
`analysis/U17_FPGA_ARCHITECTURE.md`.
The executable-RAM loading verdict and application ABI are in
`analysis/U17_EXECUTABLE_RAM_LOADING.md`; the non-transmitting planning
skeleton is `host/u17_loader_skeleton.py`.
Standalone local-control evidence and the revised critical path are documented
in `analysis/STANDALONE_STARTUP_STATE.md`, with the focused ROM comparison in
`analysis/ROM_LOCAL_CONTROL_COMPARISON.md` and the low-effort capture sheet in
`STARTUP_OBSERVATION_WORKSHEET.md`.

The U3 Edit Panel preservation and comparison report is
`analysis/EPROM_41.005.431.11-U3-EDIT-V1.1_INITIAL.md`; its reachable
disassembly is under `analysis/generated/u3/`. The unresolved-U3 audit,
functional map, protocol candidates, three-controller architecture, storage
inventory and targeted hardware observations are in:

- `analysis/U3_TASK_AUDIT.md`
- `analysis/U3_FUNCTIONAL_MAP.md`
- `analysis/U3_PROTOCOL_CANDIDATES.md`
- `analysis/THREE_CONTROLLER_ARCHITECTURE.md`
- `analysis/FIRMWARE_STORAGE_INVENTORY.md`
- `analysis/NEXT_HARDWARE_OBSERVATIONS.md`
