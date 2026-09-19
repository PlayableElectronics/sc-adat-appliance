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
then `0x02A1` branches to the failure/checksum path at `0x02CD`. The `FDFC /
FDFD` pair is `AA55`, but that pair is not reached as a successful startup
gate because the earlier `FDFE/FDFF` pair fails its `AA55` test.

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
- checksum comparison at `0x02CD` therefore **passes**.

The console failure is therefore caused by the earlier marker branch, not by
the corrected checksum loop.

## Corrected conclusion

The prior image model was incomplete and is falsified as a hardware startup
contract. `FDFC/FDFD` is checked as `AA55`, while `FDFE/FDFF` is also checked
as `AA55` before the checksum path. The same `FDFE/FDFF` bytes are then read
as the stored checksum at `0x02D7–0x0304`. This dual use is unresolved; it may
represent a combined marker/checksum convention, a bank/decode distinction,
or another startup assumption not represented by the simple linear image
model.

No replacement candidate is authorized. The original DS1230 remains
preserved, and no further write is permitted until the emulator and hardware
address/decode evidence agree on the startup contract.

## CODE versus XDATA

The checksum routine uses `MOVX`, so this emulation tests only the XDATA
hypothesis. `LCALL 0x8000` is a separate CODE fetch and is not exercised by
the checksum routine. The dump does not prove that the same DS1230 responds
to both CODE and XDATA at `0x8000`, nor that file offset zero is physically
decoded there. A bus trace of `PSEN`, `RD`, address and chip-select signals is
required before selecting a new image layout.
