# Initial firmware analysis: U17 V1.06

Analysis input is the locally preserved canonical dump named in
[`../EPROM_PRESERVATION.md`](../EPROM_PRESERVATION.md). The binary itself is
not tracked. Re-run the dependency-free analyzer with:

```sh
python3 dyaxis/analysis/analyze_8051.py \
  .local/dyaxis/eprom-dumps/41.005.415.Z1-U17-V1.06/41.005.415.Z1-U17-V1.06-AM27C256.bin
```

## Verified facts

- The image is 32,768 bytes, non-blank, and has SHA-256
  `22aa7788f49abf0c5ad31d0bc15fb2048cacaec1bac8cec0ddde87e29854e0dd`.
- The first six standard 8051 vector entries are `LJMP` instructions:
  reset `0x0000 -> 0x2F6F`, external interrupt 0 `0x0003 -> 0x3452`, timer 0
  `0x000B -> 0x3470`, external interrupt 1 `0x0013 -> 0x33F8`, timer 1
  `0x001B -> 0x348E`, and serial RI/TI `0x0023 -> 0x3416`.
- The P80C552 timer-2/capture vector at `0x002B` contains an inline register
  save/return sequence rather than the same `LJMP` shape.
- The reset entry begins with a substantial startup routine and the image has
  many valid 8051-looking control transfers, stack/register saves, and returns;
  this is consistent with executable 8051 firmware rather than a blank or
  random dump.
- Printable strings include `MultiDesk Boot ROM, version 1.06, 28-Jun-94`,
  `Copyright (C) 1994 Studer-Editech Corporation`, boot/checksum diagnostics,
  and a master-reset instruction.
- The serial interrupt vector is explicitly present at `0x0023`; its target
  `0x3416` is a candidate serial handler entry point.
- The target at `0x3416` has the shape of an interrupt routine: it saves
  registers, calls a lower-level routine, restores registers, and ends in
  `RETI` at `0x3433`.
- Repeated `MOVC`/table-indexing opcode patterns and clustered data regions
  are present, but their table meanings are not yet decoded.
- Byte values corresponding to standard 8051/P80C552 SFR addresses occur in
  the image, but this first pass does not treat raw byte occurrence as proof of
  an SFR access because code and data are interleaved. In particular, it did
  not find the simple `MOV direct,#immediate` forms for `SCON`, `TMOD`, `TH1`,
  `PCON`, `IE`, or `T2CON`; a control-flow-aware disassembly is required.

## Hypotheses and next tests

- The vector at `0x0023 -> 0x3416` is likely the UART receive/transmit ISR,
  but this requires full 8051 disassembly and tracing of `SCON`/`SBUF` reads
  and writes to distinguish RI/TI handling.
- Any control-flow-confirmed writes to `SCON`, `TMOD`, `TH1`, or `PCON` will be
  UART-initialization candidates. The actual baud rate must be derived from
  clock assumptions and timer mode, then checked against captured RS-422
  traffic.
- The dense code around the interrupt targets and the reset code likely
  contains packet framing, checksum, and command dispatch logic, but no packet
  format is asserted from strings alone.
- Repeated high-address table references in the reset and boot paths are
  consistent with lookup tables and diagnostic text tables; their semantics
  need a full control-flow disassembly.

The first pass does not yet establish a baud-rate timer setup, a complete
UART initialization sequence, a packet framing/parser routine, or a confirmed
P80C552-specific SFR access. Those require instruction-boundary-aware
disassembly and, for baud/protocol claims, captures from the real RS-422 link.

## Scope boundary

This is an initial, read-only, evidence-separated report. It does not claim a
decoded RS-422 protocol, confirmed baud rate, or complete disassembly.

## Control-flow-aware qualification

The reproducible follow-up in `analysis/generated/u17/` uses disasm51 1.0.2
with the P80C552-specific SFR/vector definition in `analysis/p80c552.mcu`.
It confirms the vector targets and the serial ISR at `0x3416`. The serial ISR
saves registers, reads external data at `MOVX DPTR=0xFED0`, calls external
target `0xFED1`, restores context and executes `RETI`. It does not directly
access `S0CON`, `S0BUF`, `TH1`, `TMOD` or `PCON` at any reachable instruction
boundary in this image. Therefore the earlier generic-SFR byte-pattern
observations are not UART findings and the baud rate remains unresolved.

The P80C552 vector at `0x002B` is SIO1/I2C, not a generic Timer 2 vector.
