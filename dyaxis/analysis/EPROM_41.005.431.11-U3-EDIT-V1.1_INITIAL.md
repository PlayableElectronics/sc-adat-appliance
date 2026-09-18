# Initial analysis: Studer-Editech U3 Edit Panel firmware

Input: the verified public image
`../firmware/original/41.005.431.11-U3-EDIT-V1.1-AM27C256.bin`.
The original local canonical file was not modified. The control-flow-aware
derived listing is `generated/u3/u3.reachable.asm`.

## Provenance and verification

- Board: `DYAXIS II CONSOLE EDIT PANEL CPU BOARD`, assembly `41.005.430.01`.
- Socket: `U3`.
- EPROM: AMD `AM27C256-95DC`, DIP-28, 32,768 bytes.
- Label: approximately `41.005.431.11 / U3 EDIT V1.1 / SEP 1994`.
- SHA-256: `7de44a1ed4ccadbafb3ef62e8f50383919c25bc32fbc6c7e74013dd4747f22b3`.
- Three independent TL866A reads using `AM27C256@DIP28` were exactly 32,768
  bytes, byte-for-byte identical, and non-blank.
- The UV window was briefly exposed during identification and was subsequently
  covered with an opaque label.

## Reproduction

The disassembly uses `disasm51` 1.0.2, pinned to source commit
`a32d0adc80cfbf203745318900ced5ea94303b15`, with the repository's exact
P80C552 SFR/vector definition:

```sh
.local/disasm51-venv/bin/disasm51 \
  --include dyaxis/analysis/p80c552.mcu \
  --entry RESET \
  dyaxis/firmware/original/41.005.431.11-U3-EDIT-V1.1-AM27C256.bin \
  > dyaxis/analysis/generated/u3/u3.reachable.asm
```

This is a reachable control-flow pass from reset plus the P80C552 vector
definitions. It does not treat the whole mostly-`0xFF` image as executable.

For the interrupt/service expansion, use the same tool with explicit vector
and Timer-0 entries:

```sh
.local/disasm51-venv/bin/disasm51 \
  --include dyaxis/analysis/p80c552.mcu \
  --entry RESET --entry 0x0103 --entry 0x0113 --entry 0x011B \
  --entry 0x0262 --entry 0x0023 --entry 0x002B \
  dyaxis/firmware/original/41.005.431.11-U3-EDIT-V1.1-AM27C256.bin \
  > dyaxis/analysis/generated/u3/u3.vectors.asm
```

## Verified instruction-level findings

Reset is `LJMP 0x00F7`. The reset path clears internal RAM, sets `SP=0xC7`,
initializes ring/state pointers, then configures the local P80C552:

```text
PCON = 0x00
IEN0 = 0x00
TMOD = 0x21       ; Timer 0 mode 1, Timer 1 mode 2
TH0/TL0 = 0xDA/0x00
S0CON = 0x40      ; serial mode 1, receive initially disabled
TH1 = 0xFD
TL1 = TH1
TR0 and TR1 set
IP0.4 set
REN set in S0CON
ET0, ES0 and EA set in IEN0
```

The main loop at `0x014C` repeatedly calls `0x0157`, `0x018E` and `0x01CE`.
The reachable pass identifies 38 labels/data targets, including these useful
paths:

- `0x0157–0x018A`: consumes a receive/ring-buffer byte from internal RAM
  `0x90–0x9F`; `0xFD` reaches the reset path, `0xFE` is sent through `S0BUF`,
  and other bytes reach `0x03F3`.
- `0x018E–0x01A8`: drains a transmit-side buffer based at internal RAM
  `0x80–0x8F`.
- `0x01A9–0x01CB`: maps the 7-bit value through the table at `0x00B2`,
  tracks the high bit, and selects an output code.
- `0x01CE–0x0201`: writes selected output bytes to `S0BUF` and updates a
  small state array at `0xA0–0xBF`; the table at `0x0202` maps values 1–32
  to selected state slots.
- `0x0253–0x025B`: sets or clears a state bit, then emits a sequence of
  values through `0x03F3`.
- `0x03F3–0x0408`: bounds an index at `0x28`, writes either `0x00` or
  `0xFF` to the state array, and dispatches through the table at `0x0411`.

These are strong signs of a compact serial edit-panel controller with input
translation and output/state mapping. They do not by themselves identify
which physical connector or peripheral owns SIO0.

## Interrupt/vector caution

Only reset is a clean `LJMP` in the conventional vector table. The external-
interrupt and Timer-1 slots contain compact `AJMP` entries; Timer 0 reaches
`0x0262` through `AJMP 0x0262`. The serial and SIO1/I2C slots contain inline
stubs, some of which overlap printable/data-looking material.
The firmware does enable Timer 0, SIO0 and global interrupts, so interrupt
entry likely uses compact inline stubs or board/compiler-specific layout. The
reachable disassembly therefore does not claim a serial ISR target from the
vector bytes alone.

## UART and timing candidate

The serial setup is confirmed at valid reset-path instruction boundaries. The
available CPU-board photograph records a `12.000 MHz` crystal for assembly
`41.005.430.01`; that marking should still be rechecked before wiring a
capture. With the documented P80C552 clock assumption of a 12-clock machine
cycle, Timer 1 mode 2, `TH1=0xFD`, `SMOD=0` gives a nominal 10,416.7 baud at
12 MHz under the ordinary 8051 UART formula. This is a timing candidate, not a
measured protocol fact.

The `0xFD` receive control and `0xFE` transmit/control handling are the best
current framing leads. No checksum, packet length, or RS-422 pin assignment
is proven by this ROM alone.

## Strings and tables

The image contains these meaningful embedded identifications:

- `0x0054`: `Copyright 1993,94 Studer Editech Corp.`
- `0x007E`: `V1.1 Edit Panel Firmware Designed by John C. Weitz`
- `0x00B2`: compact code/value translation table used by `0x01A9`.
- `0x0462–0x04EA` and `0x0639–0x0690`: channel/status-style text and
  formatting tables, including `C0`–`C?` and `S0`–`S<` patterns.

The strings are not directly referenced by the reset-reachable code, so their
display/diagnostic use remains unresolved. They are evidence of Edit Panel
firmware identity, not proof of a specific display protocol.

## Cross-ROM comparison

| Property | U3 Edit Panel | U17 MultiDesk Boot | U7 Uptown controller/fader |
|---|---:|---:|---:|
| Size | 32,768 bytes | 32,768 bytes | 16,384 bytes |
| Reset target | `0x00F7` | `0x2F6F` | `0x1E12` |
| Main evidence | compact SIO0 translation/state loop | boot, checksum, external-RAM launch | PWM, ADC, panel scan, local UART |
| Identifying text | `V1.1 Edit Panel Firmware` | `MultiDesk Boot ROM, version 1.06` | `Uptown Automation`, control-panel diagnostics |
| Shared printable strings | none found | none found | none found |
| Shared non-blank 32-byte windows | none meaningful | one window includes trailing `0xFF` padding | none |

The U3 image is therefore distinct firmware on the same broad controller
assembly family as U17. Its serial/state-machine evidence makes it a stronger
candidate for Edit Panel communication than U17 alone, while U7 remains the
strongest candidate for distributed fader and panel-I/O control.

## Boundary and next measurement

Do not transmit yet. First identify the SIO0-to-board path, any RS-422 line
transceiver part numbers, connector pins, differential-pair direction and
reference ground. Then use a high-impedance differential receiver for a
receive-only capture. The smallest useful capture is one standalone startup
and one isolated button/encoder action, with the resulting bytes correlated to
the U3 `0xFD`/`0xFE` and translation-table leads.
