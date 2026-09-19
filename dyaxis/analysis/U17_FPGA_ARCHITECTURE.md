# U17 board FPGA and external-address architecture

Date: 2026-09-18. This report reassesses the public U17/P80C552 analysis using
the existing repository photographs and notes. It does not analyze the second
Uptown Automation ROM.

## Identified devices

| Role | Visible marking | Package/reference status | Evidence |
|---|---|---|---|
| FPGA | `XILINX XC3030TM-70 PC68C` | `PC68C` identifies the 68-pin plastic leaded chip-carrier package; PCB reference is not legible | `photo/2677.jpg` |
| Companion programmable logic | `PALC22V10L-25PC`; second line `9353 000020` | Exact PCB reference designator is not legible; `PC` is the 24-pin molded-DIP PAL family suffix | `photo/fpga/2703.jpg` |
| Serial controller | Visible Zilog marking begins `Z85230...`; notes record the family and date code `9319`, but the full suffix is not clear | Exact suffix/reference require a clearer close-up | `photo/2667.jpg`, `PHOTO_FINDINGS_2026-09-06.md` |

The PAL identification is taken from the visible marking, not inferred from
package shape. It is a programmable logic array, not a configuration PROM and
not a memory device.

## Configuration consequences

XC3000 devices use volatile SRAM configuration. Xilinx documentation describes
master-serial configuration from an external serial PROM, master-parallel
configuration from a byte-wide EPROM, and peripheral mode in which a processor
supplies configuration data.

The visible PAL cannot independently store the XC3030 bitstream. It may
qualify chip selects, decode address regions, gate configuration signals, or
implement other glue logic. The two nearby FPGA-area socketed devices in
photos `2700` and `2702` remain candidates for firmware/configuration storage,
but no source is assigned without tracing `DIN`, `CCLK`, `DONE/PROG`, `INIT`,
mode pins and ROM chip-select/output lines. They are distinct from U13/U14,
which are confirmed differential-interface devices and not ROM candidates.

The U17 ROM could configure the FPGA only if the board selects peripheral mode
and the U17 code implements the loader. The current U17 disassembly establishes
neither. A master-serial or master-parallel arrangement would configure
independently at power-up before normal P80C552 operation.

## Reinterpretation of U17 missing targets

The serial ISR and other interrupt stubs call or access external addresses in
the `0xFEC0`–`0xFEF9` range. These addresses are outside the 32 KiB U17 ROM.
Given the XC3030/PAL/Z85230 hardware, the architectural possibilities include:

1. FPGA- or PAL-decoded external registers/peripherals;
2. a Z85230 register window or glue logic around it;
3. external RAM or a banked/overlay memory window;
4. a downloaded program or service region supplied by another device; or
5. a separate ROM/device selected by board decode.

The U17 image alone cannot select among these. It is not reasonable to
describe the missing targets as another ordinary ROM without bus tracing.

New board trace evidence narrows the architecture: U17 directly supplies the
P80C552 program, and the small device shown in
`photo/image-1789743641546.jpg` is the `PALC22V10L-25PC` programmable-logic
device (`9353 000020`) associated with the XC3030 scan subsystem. The XC3030
scans encoders and other console controls. The U17 `FFE1/FFE3` accesses should
therefore first be tested as a local FPGA/peripheral service-register window,
possibly decoded or controlled by the PAL. This does not
prove that the PAL owns the whole window; the PAL/FPGA may decode some or all
of it, and the Z85230 service window remains separate. See
`U17_MAIN_PROGRAM_ARCHITECTURE.md` for the address-by-address evidence.

The ROM does, however, contain a separate confirmed executable-RAM path:
`jump_03A4` clears `0x8000`–`0xFDFD`, `jump_037C` validates that span, and
`jump_328A` executes `LCALL 0x8000`. The receive-side state machine writes
`MOVX` bytes into that external window. See
`U17_EXECUTABLE_RAM_LOADING.md` for the evidence chain and ABI boundary.

## Possible FPGA roles

These are hypotheses, not confirmed assignments:

- **External CODE/XDATA decoding — strong hypothesis.** FPGA/PAL logic can
  generate chip selects and timing for the P80C552 bus. `MOVX` accesses near
  `0xFEC0` are consistent with a decoded peripheral window.
- **Interrupt-vector indirection — plausible.** FPGA/PAL logic could expose
  interrupt status or acknowledge registers in the external window. The ROM
  vector stubs do not prove the FPGA is the vector source.
- **Z85230 interfacing — plausible to strong at board level.** The photographed
  Z85230-family controller may explain why the U17 serial ISR is an external
  service shim. Exact bus wiring and channel assignment remain unknown.
- **Control-panel scanning — plausible.** FPGA logic may scan buttons, faders,
  LEDs or motor-fader timing while the P80C552 handles supervision.
- **Downloaded program memory — unresolved.** External RAM or a configuration
  path could hold downloaded logic/code, but no loader or map is confirmed.

## Preservation and next evidence

The PAL is not a safe candidate for an EPROM read. Do not select an
approximately similar PAL/GAL/PROM definition or apply a programmer operation.
If a future close-up proves that a nearby device is instead an exact FPGA
configuration PROM, first record its complete marking, pin-1 orientation,
package and bit organization. Only then select the exact supported programmer
definition and perform three independent read-only reads into a separate
configuration-dump directory; never mix that bitstream with U17 8051 code.

The next physical observation is one powered-off macro photograph that makes
the PAL PCB reference, the Z85230 full suffix/reference, both nearby ROM
references, and the FPGA configuration-pin/ROM trace area legible. Until then,
the passive RS-422 plan must remain receive-only and must account for possible
FPGA/Z85230 mediation rather than probing assumed MCU UART pins.
