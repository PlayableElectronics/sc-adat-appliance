# U17 checksum instruction table

This is a direct transcription of the U17 machine instructions at
`0x02CD..0x0311` and `0x037C..0x03A3`. It is independent of the Python
emulator implementation.

| Address | Instruction effect | Relevant state/branch |
|---|---|---|
| `02CD` | Clear `A`; set `R7=00`, `R6=80`; set `R5=FD`, copy to `R4` | checksum start `R6:R7=8000`; endpoint supplied as `R4:R5=FDFD` |
| `02E8` | `DPTR=FDFE`; `MOVX A,@DPTR`; `R4=A` | read stored high byte |
| `02EB` | increment `DPTR`; `MOVX A,@DPTR`; `CJNE A,R7,0311` | read stored low byte; mismatch -> Failed |
| `02F0` | `MOV A,R6`; `CJNE A,R4,0311` | high-byte mismatch -> Failed |
| `02FD` | FE06 display call with string `Checksum Good...` | successful checksum path |
| `0311` | FE06 display call with string `Checksum Failed...` | either comparison mismatch |
| `037C` | Save endpoint `R4:R5` to internal `26:27`; clear `R4:R5` | 16-bit accumulator is `R4:R5`, high:low |
| `0383` | `SETB C; A=R7; SUBB A,27h; A=R6; SUBB A,26h; JNC 039D` | unsigned termination test; endpoint is exclusive |
| `038E` | `DPL=R7; DPH=R6; MOVX A,@DPTR` | read one XDATA byte |
| `0391` | `ADD A,R5`; `R5=A`; clear `A`; `ADDC A,R4`; `R4=A` | 8-bit low sum plus carry into high byte |
| `0397` | increment `R7`; if zero increment `R6`; loop to `0383` | address advances by one |
| `039D` | complement `R5` into `R7`; complement `R4` into `R6`; `RET` | result returned as `R6:R7` |

## Exact access order

The marker gate at `0x0293` is separate control flow: it reads `FDFE`, then
`FDFF`, then `FDFC`, then `FDFD`. If either pair is not `AA55`, execution
deliberately enters `0x02CD`; no value change is required.

For the checksum path, `0x037C` reads exactly:

```text
CPU XDATA 0x8000 through 0xFDFC inclusive
file offsets 0x0000 through 0x7DFC inclusive
Python slice image[:0x7DFD]
```

It performs 32,253 `MOVX` reads. There are no `MOVX` writes in
`0x02CD..0x0311` or `0x037C..0x03A3`. After return, the stored checksum is
read high byte first at `FDFE`, then low byte at `FDFF`; comparisons are low
byte (`R7`) first at `0x02EB`, then high byte (`R6`) at `0x02F0`.

For the existing candidate, the independent calculation is `FDD7`, stored
big-endian at file offsets `0x7DFE=FD` and `0x7DFF=D7`.
