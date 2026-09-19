# U17 memory map: evidence and hardware hypotheses

This report separates address-space facts recovered from U17 instructions from
physical-chip assignments inferred from the new board photographs.

| Space/range | Static evidence | Physical interpretation | Confidence |
|---|---|---|---|
| CODE `0000..7FFF` | U17 is a 32 KiB EPROM; reset and reachable code occupy this range | U17 AMD AM27C256 | Confirmed |
| XDATA `0000..7FFF` | Reset loop at `2F7D` writes zero for `0x8000` bytes | U18 Toshiba TC55257BSPL-10 is the strongest volatile-RAM candidate | Strong hardware hypothesis |
| XDATA `8000..FDFC` | Checksum loop `037C` and clear loop `03A4` access this span | DS1230-backed persistent/application region is the best fit | Strong hypothesis |
| XDATA `FDFC..FDFF` | Signature and checksum metadata are read; checksum bytes are explicitly cleared | Likely persistent metadata within the same upper RAM device | Strong hypothesis |
| XDATA `FE00..FFFF` | Reset loop at `2F8B` clears this range separately; service accesses include `FFE1/FFE3`, `FFF0/FFF1`, `FFF4/FFF5` | External peripheral/service decode, not proven DS1230 storage | Strong static conclusion; exact devices unresolved |
| CODE `8000` | `328A` executes `LCALL 8000` after validation | External application entry, provider unresolved | Confirmed code behavior |
| CODE `FE00..FEF9` | Literal `LCALL` targets and interrupt shims | Mapped executable provider, possibly persistent memory, executable RAM or FPGA/PAL bus logic | Confirmed target; provider unresolved |

The `u17-memory-ranges.tsv`, `u17-checksum-ranges.tsv` and
`u17-update-writes.tsv` files are the machine-readable evidence tables. CODE
fetches are never treated as MOVX/XDATA peripheral accesses.
