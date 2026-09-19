# U17 complete reachable program map

Generated from `u17.reachable.asm` and the verified tracked ROM. The map covers
**1831 valid instruction records** across **181 labeled regions**;
it is a complete reachable-vector map, not a claim that unreachable ROM bytes
are non-code. External CODE calls remain unresolved dependencies.

## Address-space boundaries

- CODE: U17 physical ROM `0x0000..0x7FFF`; external CODE targets are listed in
  `u17-external-code-dependencies.tsv`.
- Internal RAM/SFR: P80C552 direct/register operations at valid instruction
  boundaries only.
- XDATA: literal DPTR references are listed in `u17-xdata-xrefs.tsv`; external
  RAM/program window and service windows are not conflated.

## Confirmed entry families

- Reset/startup: `0x0000 -> 0x2F6F -> 0x2FD2 -> 0x01E0`.
- Local checks/services: `0x037C`, `0x03A4`, `0x032F`, `0x034D`, `0x1440`.
- Main service state machine: `0x30A7..0x328A`.
- Interrupt shims: `0x33F8`, `0x3416`, `0x3434`, `0x3452`, `0x3470`,
  `0x348E`, `0x34AC..0x357E`.

Indirect/table references are preserved in `u17-indirect-targets.tsv`; no
indirect target is silently promoted to a protocol or peripheral assignment.
