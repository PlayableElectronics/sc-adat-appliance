# U17 DS1230 layout: preservation hypothesis

The new photograph identifies a Dallas `DS1230Y-100` 32K x 8 battery-backed
nonvolatile SRAM on the U17 board. It is preservation-critical, but the ROM
does not prove the chip-select wiring or address decode.

## Best-supported layout

| Range | Evidence | Assessment |
|---|---|---|
| `8000..FDFC` | Reset clear, receive transfer writes, checksum input | Strong candidate for persistent application/data contents |
| `FDFC..FDFF` | `AA 55` signature at `FDFC/FDFD`; complemented checksum compared at `FDFE/FDFF` | Candidate persistent header/trailer; exact ownership is not electrically proven |
| XDATA `FE00..FFFF` | Separately cleared at reset and used for service windows | Evidence weighs against mapping this entire XDATA range to DS1230 storage |
| CODE `FE00..FE7F` | Dump contains 43 three-byte `LJMP` trampolines; `FE06 -> 075D`, `FE33 -> 2182`, `FE60 -> 037C` | Strong evidence DS1230 supplies the external CODE trampoline table under the proposed `8000` mapping |

The DS1230 is 32 KiB, while `8000..FDFF` is `0x7E00` bytes; therefore the
remaining `0x0200` bytes of a full 32 KiB device could be bank-select,
reserved, mirrored, or part of an unobserved decode. A simple one-to-one
`8000..FFFF` assignment is not established. The most conservative statement
is “DS1230 is a plausible source for the persistent upper application window
and is strongly evidenced as the CODE provider for the FE trampoline table;
the corresponding XDATA decode remains unresolved.”

Do not read it with an EPROM definition or remove it. A safe preservation path
is first a powered-off, non-invasive pinout/continuity review and chip-select
trace, followed by a reviewed high-impedance in-system read plan. The plan
must account for the age of the internal battery and preserve power state; no
powered probing, write/update, blank-check, erase, or programmer operation is
authorized by this report. If the read plan is approved, acquire three
read-only dumps with an independently verified byte count and SHA-256 while
preserving the raw captures separately from U17 executable code.
