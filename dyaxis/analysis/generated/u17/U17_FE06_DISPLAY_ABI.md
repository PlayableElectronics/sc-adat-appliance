# U17 FE06 display/string ABI

The resolved call-site data-flow pass finds **16** calls to
external CODE `0xFE06` with definite register values. In every definite case,
`R2:R1` is a 16-bit CODE-space pointer into the U17 ROM and resolves to one of
the embedded boot/status strings. This is strong evidence that `FE06` is an
external display/string service, not an XDATA peripheral register.

| Field | Observed evidence | Interpretation |
|---|---|---|
| `R2:R1` | Pointers resolve to `14` embedded strings | Confirmed CODE-space string pointer |
| `R3` | Values: R3=0x05 | Meaning unresolved; compare with display layout before assigning |
| `R5` | Values: R5=0x01, R5=0x02, R5=0x03, R5=0x04, R5=0x05, R5=0x06, R5=0x07 | Meaning unresolved; repeated values may encode an operation/style/destination, but no assignment is proven |
| `R4`, `R6`, `R7` | Recorded per call in `u17-fe06-calls.tsv` | Inputs are preserved; no unsupported semantic label |

The exact pointer, caller, all resolved register values and nearby post-call
instructions are in `u17-register-resolved-abi.tsv`. The FE06-specific view is
`u17-fe06-calls.tsv`; referenced strings are in
`u17-referenced-strings.tsv`.

The preserved DS1230 FE trampoline table resolves the external entry itself:
`FE06` contains `LJMP 075D` under the proposed mapping. This is strong evidence
that FE06 dispatches into U17 CODE through DS1230-provided glue, while the
display operation's internal semantics remain defined by the target routine
and its hardware accesses.

No screen-row or column meaning is assigned to R3/R5 from static code alone.
Photographed display geometry and a passive bus trace are required for that
mapping.
