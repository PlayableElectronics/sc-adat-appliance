# U3 provisional serial protocol candidates

This report separates byte handling proven in U3 code from meanings that need
a wire capture. It does not claim RS-422 ownership, a checksum, or a measured
baud rate.

## Producers and consumers

| Value/context | Valid code locations | Proven behavior | Confidence of protocol meaning |
|---|---|---|---|
| `0xFD` received | `0x0157–0x017D` | branches to `LJMP 0x00F7`, resetting U3 | High: local reset/control sentinel; wire delimiter unknown |
| `0xFE` received | `0x0157–0x0177` | writes the same accumulator byte to `S0BUF` immediately | Medium: special echo/ack/control value; escaped data not proven |
| `0xFF` received | `0x0157–0x0170`, `0x0253–0x025B` | invokes a 39-step state/output update through `0x03F3` | Medium: local command/sentinel; packet role unknown |
| `0xFE` generated for scan | `0x02D0–0x02EE` | rotated P4 scan selector, unrelated to serial parsing | High: same literal has a separate hardware-scan use |
| `0x80..0xF0` event groups | `0x02F0–0x03D7` | encode changed P5 bits and scan group before TX queueing | Medium-high: controller event code family |
| output translation | `0x01A9–0x01CB`, table `0x00B2` | maps 7-bit values to a table-selected output code | Medium: translation layer, not a packet field map |

## Buffer/state machine

The SIO0 ISR receives into a 16-byte ring at `0x90–0x9F`; pointers/count are
`0x61` (write), `0x60` (read), and `0x62` (count). Panel scan changes queue
into a second 16-byte ring at `0x80–0x8F`; pointers/count are `0x5E`, `0x5D`,
and `0x5F`. The main loop alternates receive consumption, scan/output service,
and transmit consumption at `0x014C`.

This supports a byte-stream event protocol more strongly than a self-contained
length-prefixed packet parser. U3 contains no reachable compare/accumulate
routine that establishes a packet length or checksum over the RX ring. There is
also no proven address field: the `0x80..0xF0` groups are scan/event encoding,
not demonstrated board addresses.

## Provisional command dictionary

| Candidate | Meaning | Evidence | Confidence |
|---|---|---|---|
| `FD` | reset U3 / reset-state escape | `0x017D` unconditional `LJMP 0x00F7` | High locally; low on wire semantics |
| `FE` | immediate transmit/echo or control byte | `0x0177` writes S0BUF; separate `0x02D0` scan selector | Medium |
| `FF` | state/output exercise or bulk update trigger | `0x0170` calls `0x0253`; 39 indexed updates | Medium |
| `80..F0 + index` | input-change event family | `0x02F0–0x03D7`, per-bit queueing | Medium-high |
| second event byte | polarity/state transition and/or translated value | `0x03DA` receives encoded event and writes TX ring | Medium |

No supported U3 evidence identifies fields for address, command, payload length
or checksum. The `0x0411` indirect jump table must not be promoted to a command
dispatch table until its targets are resolved.

## Cross-ROM compatibility search

U17 uses an external service window around `0xFEC0–0xFEF9` and its serial ISR
at `0x3416` delegates through `0xFED0/0xFED1`; it does not share U3's direct
S0BUF/ring implementation. U7 directly initializes S0CON/S0BUF at `0x1CA9`
and transmits via `0x21EA`, but its recovered literals do not establish the
U3 `FD/FE/FF` or `0x80..F0` event family. No meaningful common non-blank code
window or printable protocol vocabulary was found.

The current best hypothesis is that U3 is a local Edit Panel serial endpoint,
U7 is a separate fader/I/O endpoint, and U17/FPGA/Z85230 provide boot or
supervisory services. Whether any of these serial paths converge at the rear
RS-422 ports is unresolved.
