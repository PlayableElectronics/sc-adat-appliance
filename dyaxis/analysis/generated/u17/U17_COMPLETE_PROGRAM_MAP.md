# U17 current reachable-vector map

Generated from `u17.reachable.asm` and the verified tracked ROM. The current
pass reconstructs exact ROM addresses for **1830 valid instructions**
covering **2950 bytes**. It is not a complete program map: bytes
outside reachable vector paths, unresolved indirect control flow and external
CODE bodies remain separate evidence domains.

Referenced strings: **0**; printable candidates not
referenced by a literal ROM pointer or resolved MOVC base: **66**.
See `u17-code-classification.json` for complete byte coverage and percentages.

## Confirmed entry families

- Reset/startup: `0x0000 -> 0x2F6F -> 0x2FD2 -> 0x01E0`.
- Local checks/services: `0x037C`, `0x03A4`, `0x032F`, `0x034D`, `0x1440`.
- Main service state machine: `0x30A7..0x328A`.
- Interrupt shims: `0x33F8`, `0x3416`, `0x3434`, `0x3452`, `0x3470`,
  `0x348E`, `0x34AC..0x357E`.

Exact instruction addresses are present in generated TSVs. MOVC tables are in
`u17-movc-tables.tsv`; only bounded target sets are eligible for promotion.
