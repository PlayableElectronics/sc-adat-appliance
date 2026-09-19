# Powered-off DS1230 continuity table

This is a measurement plan, not a claimed map. Disconnect power completely,
discharge safely, and use continuity/ohms only. Do not power the board or
programmer during this check. Record the destination reference designator and
pin for every beep; do not infer a connection from a nearby trace.

The Dallas `DS1230Y-100` is DIP-28. Pin names below are the standard 32K × 8
SRAM pinout to verify against the device datasheet before probing:

| DS1230 pin | Signal | Trace to record |
|---:|---|---|
| 1 | A14 | P80C552/bus-buffer/PAL-side A14 destination |
| 2 | A12 | bus-buffer/PAL-side A12 destination |
| 3 | A7 | bus-buffer/PAL-side A7 destination |
| 4 | A6 | bus-buffer/PAL-side A6 destination |
| 5 | A5 | bus-buffer/PAL-side A5 destination |
| 6 | A4 | bus-buffer/PAL-side A4 destination |
| 7 | A3 | bus-buffer/PAL-side A3 destination |
| 8 | A2 | bus-buffer/PAL-side A2 destination |
| 9 | A1 | bus-buffer/PAL-side A1 destination |
| 10 | A0 | bus-buffer/PAL-side A0 destination |
| 14 | GND | ground/reference only |
| 20 | /CS | PAL/FPGA/glue decode destination |
| 21 | A10 | bus-buffer/PAL-side A10 destination |
| 22 | /OE | CPU read-control/buffer destination |
| 23 | A11 | bus-buffer/PAL-side A11 destination |
| 24 | A9 | bus-buffer/PAL-side A9 destination |
| 25 | A8 | bus-buffer/PAL-side A8 destination |
| 26 | A13 | bus-buffer/PAL-side A13 destination |
| 27 | /WE | CPU write-control/buffer destination |
| 28 | VCC | do not inject power; identify supply net only |

Also record continuity from the corresponding U18 `TC55257BSPL-10` address and
control pins to the same bus/buffer/PAL area. The required comparison is:

```text
DS1230 A0..A14 ↔ U18 A0..A14 ↔ bus-buffer/CPU address nets
DS1230 /CS,/OE,/WE ↔ U18 /CS,/OE,/WE ↔ PAL/FPGA/glue and CPU controls
```

Do not call the mapping linear unless all address lines and control ownership
are measured. In particular, continuity alone cannot prove dynamic bank
selection; it only identifies the nets that a later passive powered capture
would need to observe.
