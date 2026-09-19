# U17 high-address XDATA and service-window map

This table is an exhaustive map of literal high-address references found in
the reachable U17 disassembly. CODE call targets and XDATA addresses are kept
separate. “Role” is an evidence-qualified interpretation, not a claim that
the address is a Macintosh register.

## XDATA `0xFFE0..0xFFFF`

| Address | Direction | ROM locations/functions | Values/behavior | Likely role |
|---|---|---|---|---|
| `FFE0` | none found | — | No literal reachable access | Unresolved |
| `FFE1` | R/W | `30AA`, `3253`, `3332`, `3348` | bit 0 gates service-byte availability; bit 2 gates timer/status return; `3332` writes `09`, `C0`, derived values; `3348` writes fixed init sequence | Candidate FPGA/peripheral service-register window, possibly decoded or controlled by PAL |
| `FFE2` | none found | — | No literal reachable access | Unresolved |
| `FFE3` | R/W | `30C3`, `327E` | read into internal `A5`; write `R7` after timeout/service routine | one-byte mailbox data/status register; exact producer is external |
| `FFE4..FFEF` | none found | — | No literal reachable access in this range | Unresolved |
| `FFF0` | R | `1440` | after `FFF1=F0`, delay, `FFF1=47`; `05→1`, `0A→2`, otherwise `0` | startup peripheral identity/status response |
| `FFF1` | W | `1440` | writes `F0`, then `47` | startup peripheral command/select register |
| `FFF2..FFF3` | none found | — | No literal reachable access | Unresolved |
| `FFF4` | W | `0542`, `0646` | multi-byte records: `R3`, `0F`, masked `R2`, `08`, then data; `0646` uses computed address fields | external transfer/display/service data port; only reached by loader/transfer routines |
| `FFF5` | W | `0542`, `0646` | always writes `0E` before `FFF4` sequence | external transfer/service command/index port |
| `FFF6..FFFF` | none found | — | No literal reachable access | Unresolved |

The ROM contains no indirect literal evidence that reclassifies the unused
addresses above. Computed `MOVX` accesses in the ordinary external-RAM window
are kept separate; the download path computes destinations beginning at
`0x8000` and does not establish a generic `0xFFE0` register bank.

## Related service and interrupt windows below `0xFFE0`

| XDATA read address | U17 ISR/service entry | CODE target | Evidence |
|---|---:|---:|---|
| `FEC0` | `3452` | `FEC1` | external interrupt 0 shim |
| `FEC4` | `3470` | `FEC5` | timer/interrupt shim |
| `FEC8` | `33F8` | `FEC9` | external interrupt 1 shim |
| `FECC` | `348E` | `FECD` | interrupt shim |
| `FED0` | `3416` serial vector | `FED1` | serial service shim |
| `FED8..FEF8` even addresses | `34AC..357E` | next odd address | additional P80C552 peripheral interrupt shims |

Each ISR saves context, reads one external byte into PSW, calls the adjacent
external CODE target, restores context and returns `RETI`. The ROM does not
contain the handler bodies, so these entries cannot identify Z85230 channels
or host packet fields by themselves.

## Other related accesses

- `FE00` is cleared as XDATA over `FE00..FEFF` during reset; `LCALL FE00` is a
  separate external CODE call in startup and must not be conflated with that
  XDATA write window.
- `FEEE/FEEF` are written during startup as a separate adjacent pair (`32/C9`);
  they are below the `FFE0..FFFF` table and their peripheral role is not
  identified.
- `FDFC..FDFF` hold checksum/signature values used by startup validation.
- `8000..FDFD` is the external RAM/program window used by checksum, download
  and `LCALL 8000` launch logic.

The highest-confidence mailbox interpretation is `FFE1/FFE3`; `FFF0/FFF1`
looks like a separate startup identification exchange, and `FFF4/FFF5` is
confined to the transfer path. None is a proven Macintosh wire interface.
