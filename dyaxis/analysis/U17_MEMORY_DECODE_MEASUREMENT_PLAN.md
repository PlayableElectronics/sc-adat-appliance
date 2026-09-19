# U17 checksum decode measurement plan

This plan is a follow-up to the stable DS1230 read and the failed `de42ce8`
physical test. It is deliberately limited to deciding which device responds to
the startup reads; it does not authorize another image or any transmission.

## Proven versus falsified

- Three post-test `DS1230Y(RW)` reads were identical and matched the candidate
  byte-for-byte, including `FDFE/FDFF = FDD7` and the retained `FE00..FFFF`
  suffix.
- The instruction-level model reaches `0x02CD`, computes `FDD7`, and predicts
  `0x02FD` (`Checksum Good`) under `file offset = XDATA address - 0x8000`.
- The console displayed `Checksum Failed` (`0x0311`). The simple linear XDATA
  mapping is therefore falsified by hardware.
- It is not proven that DS1230 and U18 share the same address bus decode, or
  that CODE fetches and MOVX reads select the same physical device.

## Minimum powered-off continuity work

Do this with the console disconnected from power, the DS1230 removed only if it
is already safe to do so, and no continuity tester connected while energized.
Use the package datasheets to map the board package pin numbers; do not infer a
pin number from the photograph alone.

1. Trace the P80C552 external-bus nets: `A15..A0`, data `D7..D0`, `PSEN`,
   `RD`, `WR` and any `ALE`/address-latch output.
2. At the DS1230Y-100, trace all `A14..A0`, `DQ7..DQ0`, `/CE`, `/OE`, `/WE`,
   `VCC` and `GND`. The essential comparison endpoints are DS `/CE`, `/OE`
   and `/WE`, plus `A15`-equivalent bank/decode input if present; the DS1230
   has only `A14..A0`, so any CPU `A15` selection must be external.
3. Repeat the same continuity checks at U18 `TC55257BSPL-10`: all address and
   data bus lines, `/CE`, `/OE`, `/WE`. Record whether the SRAM and DS1230
   controls are direct CPU signals or pass through the logic devices.
4. Trace only the PALC22V10 and XC3030 pins that connect to DS `/CE`, U18
   `/CE`, `/OE`, `/WE`, any bank/latch output, and the CPU `PSEN/RD/WR` nets.
   This identifies whether either programmable-logic device can select a
   different memory for CODE and MOVX without requiring a full board netlist.
5. Check continuity from CPU `PSEN` to the DS1230/U18 control network and from
   CPU `RD`/`WR` to each SRAM control network. Do not beep through powered
   circuits or inject voltage into the board.

The decisive result is a table of endpoints for DS `/CE`, U18 `/CE`, and any
PAL/FPGA bank signal, with common-bus versus separate-bus status. No device
should be removed to make this measurement unless its marking or a documented
net requires it.

## Smallest powered capture, only if continuity is inconclusive

Use a high-impedance, 5 V-tolerant logic analyzer with a common board ground.
Do not attach Arduino TTL UART inputs to the address/data bus and do not drive
any signal. Capture these channels:

- DS1230 `/CE`, `/OE`, `/WE`;
- U18 `/CE`, `/OE`, `/WE`;
- CPU `PSEN`, `RD`, `WR`;
- CPU `A15..A8`, plus `A7`, `A1`, and `A0` (capture all `A15..A0` if channels
  permit);
- one shared ground/reference.

Trigger on the first DS/U18 control assertion with CPU `A15..A8 = 0xFD` and
  retain the window around the four addresses `FDFC..FDFF`. The low address
  bits distinguish the two marker bytes from the two checksum bytes. If no
  memory `/CE` asserts, capture the PAL/FPGA bank-control output identified by
  continuity instead. Do not probe the differential RS-422 lines for this
  question.

Precautions: power down before attaching clips; verify analyzer ground and
input voltage rating; use short ground leads; attach only passive/high-Z inputs;
power up only after a second person or photograph review of the connections;
power down before removing them. The capture should answer whether `FDFE` is
read from DS1230 or U18 during `MOVX`, and whether `PSEN` selects a different
source. Stop after one boot/checksum window.

## Leading decode hypotheses

1. **Separate CODE/XDATA chip selects (leading):** DS1230 supplies the FE
   trampoline CODE window while U18 or a peripheral decode supplies MOVX
   `FDFE/FDFF`.
2. **PAL/FPGA bank control:** a latch or programmable-logic output changes the
   memory visible to `FDFE` between CODE, MOVX, or startup phases.
3. **Nonlinear DS1230 mapping:** DS1230 responds to the checksum XDATA range
   through a board offset or bank, so the programmer image offset is not
   `XDATA - 0x8000`.

These are hypotheses only. The single highest-value observation is the chip
select asserted during the U17 `MOVX` reads at `FDFC..FDFF`, alongside `PSEN`
and the address bus.
