# Known facts and confidence

| Fact | Confidence | Evidence |
|---|---:|---|
| Dyaxis began as an IMS Macintosh-based hard-disk audio workstation and was acquired/marketed by Studer Editech. | High | Sound On Sound 1990; Studer publications |
| The controller family includes a dedicated MultiDesk/Edit Controller with transport and scrub controls. | High | 1994 Mix review; Reverb listing; period advertising |
| The described MultiMix surface has eight faders in two banks of four. | High for the reviewed MultiMix variant | Mix 1994 |
| The reviewed surface has four assignable knobs/shaft encoders and fourteen soft switches. | High for the reviewed MultiMix variant | Mix 1994 |
| A Kensington trackball and QWERTY keyboard use ADB in the described system. | High for the reviewed MultiMix variant | Mix 1994 |
| The user's surface operates normally when its computer host software responds. | High | User test |
| The rear panel has two ADB ports, two ports explicitly labelled `(RS422) SERIAL 1/2`, a `METER POWER +5V (2A MAX.)` connector and a separate `NETWORK` connector. | High | Rear-panel photo 2865 |
| The surface includes a VFD, knobs, buttons, motorised faders, trackball and keyboard. | High | User inspection |
| The user's exact surface contains three MCU boards. | User observation; individual photographed boards support a distributed-controller design | Photos 2665-2699 |
| The working ADB keyboard/trackball bridge uses a classic Arduino Nano-compatible ATmega328P/CH340 at 5 V and 16 MHz, connected by USB serial to Linux. | High | Working implementation and capture |
| The connector board is labelled Studer Editech Multi-Desk I/O Panel, assembly 41.005.440.20. | High | Photos 2867, 2868 |
| The function and electrical protocol of the separately labelled NETWORK port are unknown; Ethernet is not yet established. | High that the port exists; protocol unknown | Photos 2865-2868 |
| Main board is labelled Dyaxis II Console Edit Panel CPU Board, assembly 41.005.430.01, Aug 1993. | High | Photo 2676 |
| At least two boards use Philips P80C552-5 8051-family MCUs. | High | Photos 2671, 2676 |
| Multiple boards share the same P80C552 CPU family and socketed program EPROMs. | High | New close-ups; user confirmation |
| FPGA-area photo visibly marks the large device `XILINX XC3030TM-70 PC68C`; `PC68C` identifies the 68-pin plastic leaded chip-carrier package. | High | Photo 2677 |
| A fader board is labelled UPTOWN AUTOMATION, CONTROLLER FADER, ASSY 935 REV B. | High | Photo 2694 |
| A verified 16 KiB U7 EPROM from the Uptown Automation controller/fader board is publicly preserved as `firmware/original/490-0270-MI-V2.7-M27C128.bin`. | High | Three identical reads; photos 2694-2695; preservation record |
| A Zilog Z85230-family serial controller is present. | Medium-high | Photo 2667; suffix needs confirmation |
| Socketed firmware and programmable devices are present. | High | Photos 2672-2674, 2676 |
| FPGA area contains at least two socketed Studer-labelled ROMs and a `PALC22V10L-25PC` programmable logic device marked `9353 000020`; its PCB reference is not legible in available photos. | High | Photos fpga/2700, 2702, 2703 |
| A public Dyaxis controller schematic/service manual is available. | Not found | Search status 2026-09-06 |
| The controller performs standalone startup with no original Macintosh host connected: motorized faders move, LEDs light, and displays show text. | High | Owner's standalone power-up observation, 2026-09-18 |
| Standalone behavior is best explained by a distributed combination of U17 boot/diagnostic code, Uptown U7 local-control firmware, FPGA/PAL glue and serial/peripheral services; host download is not required for all operation. | Medium-high | U17/U7 disassembly plus standalone observation; exact ownership of display and transport services remains open |
| New board trace evidence places U17/P80C552 as the system leader, a smaller PIC as an XC3030 communication partner, and the XC3030 as the encoder/console-control scanner. | Medium | Owner-provided physical trace evidence; PIC marking/reference still unreadable in repository photos |
| U17 XDATA `0xFFE1/0xFFE3` is a local external-service/mailbox candidate, not a proven Macintosh protocol; its `01/02/06/FF` values have state-dependent local effects. | High for code effects; medium for hardware role | U17 reachable disassembly, `U17_MAIN_PROGRAM_ARCHITECTURE.md`, `U17_HIGH_ADDRESS_MAILBOX.md` |
| U3 is an AMD AM27C256-95DC containing Studer-Editech `U3 EDIT V1.1` firmware from the `DYAXIS II CONSOLE EDIT PANEL CPU BOARD`, assembly `41.005.430.01`. | High | Three identical reads; board/chip markings |
| U3 Timer-0 firmware scans nine P5 samples through P4-selected rows and queues changed input bits; it also multiplexes two eight-byte output buffers through P4/P3. | High for MCU behavior; physical signal assignment unresolved | `analysis/U3_FUNCTIONAL_MAP.md`, `generated/u3/u3.vectors.asm` |
| Additional supplied close-ups show `AM26LS32PC` at U4 and `SN75174N` at U13 as differential line-interface candidates, and show the standalone U17 boot/checksum text on the display. | High for visible markings/observation; connector routing unresolved | Photos `image-1789744696234.jpg` and `image-1789744598797.jpg` |
