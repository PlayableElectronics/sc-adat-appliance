# U17 checksum/signature failure emulation

The two-byte `SJMP $` candidate was programmed and read back byte-for-byte,
but the console displayed `Checksum Failed...`. Three post-console DS1230
reads are unchanged from the candidate, so the failure is not caused by a
write/readback mutation.

## Exact startup result for `de42ce8`

Under the explicit offline hypothesis `file_offset = CPU XDATA - 0x8000`:

| CPU address | File offset | Read value | U17 use |
|---|---:|---:|---|
| `FDFE` | `7DFE` | `FD` | first startup marker high byte |
| `FDFF` | `7DFF` | `D7` | first startup marker low byte |
| `FDFC` | `7DFC` | `AA` | second startup marker high byte |
| `FDFD` | `7DFD` | `55` | second startup marker low byte |

At `0x029C`, `FD ^ 55 != 0`, so the conditional branch reaches `0x02A1`,
then `0x02A1` branches to the checksum path at `0x02CD`. This is not yet the
failure display path. The `FDFC/FDFD` pair is `AA55`, but the earlier
`FDFE/FDFF` pair fails its marker test.

## Instruction-accurate checksum result

The emulator in `u17_checksum_emulator.py` models the actual instructions:

- `0x02CD` sets `R6:R7 = 0x8000` and `R4:R5 = 0xFDFD`.
- `0x037C` copies the exclusive endpoint to internal `0x26:0x27`, clears
  `R4:R5`, and loops while the unsigned 16-bit `R6:R7 < 0xFDFD`.
- Each iteration reads `MOVX A,@DPTR`, adds the byte to `R5`, propagates carry
  into `R4`, increments `R7`, and increments `R6` on low-byte wrap.
- It complements `R4:R5` into `R6:R7` and returns.

For the candidate, 32,253 bytes are read at CPU addresses `0x8000–0xFDFC`
and file offsets `0x0000–0x7DFC`. The final values are:

- sum `R4:R5 = 0x0228`;
- complemented result `R6:R7 = 0xFDD7`;
- stored bytes read at `FDFE/FDFF = 0xFDD7`;
- low-byte comparison at `0x02EB` passes;
- high-byte comparison at `0x02F0` passes;
- the final path is `0x02FD`, which displays **Checksum Good**.

The console instead displayed **Checksum Failed**. Therefore the complete
linear-XDATA prediction is falsified as a physical mapping hypothesis; the
earlier marker branch does not itself explain the observed failure.

## Corrected conclusion

The prior image model was incomplete and is falsified as a hardware startup
contract. `FDFC/FDFD` and `FDFE/FDFF` are checked as marker pairs; a marker
mismatch deliberately enters the checksum path. The same `FDFE/FDFF` bytes
are then read as the stored checksum. Under the assumed mapping, the candidate's `FDD7`
matches the computed `FDD7` and predicts the success display at `0x02FD`, but
hardware produced the failure display at `0x0311`. This leaves the linear
XDATA contents or another part of the physical startup model unconfirmed.

No replacement candidate is authorized. The original DS1230 remains
preserved, and no further write is permitted until the emulator and hardware
address/decode evidence agree on the startup contract.

## Second physical failure and bounded uCsim result

The same candidate was physically programmed and read back byte-for-byte a
second time on 2026-09-20. The console again displayed `Checksum Failed...`.
This is a second confirmed physical failure, not evidence of Dallas data loss.
The candidate is diagnostic evidence only; the operator must restore the
canonical original using the guarded restore procedure.

The bounded uCsim run was not allowed to infer a breakpoint from the generic
`Stop at ... stepped ...` message. With candidate CODE and candidate XDATA,
default uCsim P80C552 behavior, and no FPGA/PAL/Z85230 stubs, the run consumed
the 200,000-instruction limit without reaching `0x0293`, `0x02CD`, `0x02FD`, or
`0x0311`. The captured state was `PC=0x33EC`, `DPTR=0xFFF6`, `ACC=0x80`,
`SP=0xD3`, and `Inst=200000`. Thus no checksum or display path was executed
by uCsim; the following read sequence is the independent instruction-level
model of the reachable static U17 bytes, not a claim about that run:

| PC | MOVX address | Candidate value | Use |
|---|---|---:|---|
| `0296` | `FDFE` | `FD` | first marker high byte |
| `0299` | `FDFF` | `D7` | first marker low byte |
| `02A3` | `FDFC` | `AA` | second marker high byte |
| `02AA` | `FDFD` | `55` | second marker low byte |
| `02E8` | `FDFE` | `FD` | stored checksum high byte |
| `02EB` | `FDFF` | `D7` | stored checksum low byte |

The modeled branch is `0293 -> 02CD -> 037C -> 02E8 -> 02EB -> 02F0 ->
02FD`, i.e. **Checksum Good** under one linear XDATA image. No MOVX writes
occur in this interval. The marker mismatch is the deliberate reason control
enters checksum validation; the bytes do not need to change between reads.
The remaining discrepancy is between this linear-XDATA prediction and the
physical display result.

## CODE versus XDATA

The checksum routine uses `MOVX`, so this emulation tests only the XDATA
hypothesis. `LCALL 0x8000` is a separate CODE fetch and is not exercised by
the checksum routine. The dump does not prove that the same DS1230 responds
to both CODE and XDATA at `0x8000`, nor that file offset zero is physically
decoded there. A bus trace of `PSEN`, `RD`, address and chip-select signals is
required before selecting a new image layout.
