# U17 checksum memory-decode logic-analyzer procedure

Purpose: identify which memory device supplies the P80C552 `MOVX` reads during
startup checksum validation. This is a passive observation only. It does not
authorize a Dallas write, serial transmission, firmware change, or probing of
RS-422.

## Preconditions

1. Restore the canonical DS1230 image with the guarded procedure if it is not
   already restored. Do not create another candidate.
2. Power the console fully off before attaching probes. Use ESD protection.
3. Complete the powered-off continuity table in
   `U17_DS1230_CONTINUITY_TABLE.md` first. Record actual board net names and
   PAL/FPGA destinations; do not assume the table is a schematic.
4. Use a high-impedance, 5 V-tolerant analyzer. Verify its maximum input
   voltage, common ground, short ground leads, and passive inputs before
   powering the console.

## Channels

Minimum useful capture channels:

| Channel group | Signals |
|---|---|
| CPU controls | `PSEN`, `RD`, `WR` |
| CPU address | `A15..A0`; if channel-limited, at minimum `A15..A8`, `A1`, `A0` |
| DS1230 controls | `/CS`, `/OE`, `/WE` |
| U18 TC55257 controls | `/CS`, `/OE`, `/WE` |
| Decode | any PAL/FPGA bank-control net identified by continuity |
| Reference | one board ground point |

Do not connect the analyzer to the DS1230 data pins unless the analyzer has
enough inputs and the connection has been reviewed. The first question is chip
select ownership, not data decoding.

## Capture

1. Set digital thresholds appropriate for the board's measured logic supply;
   do not assume 3.3 V levels on a 5 V board.
2. Configure a single-shot capture at the highest practical sample rate with
   enough pre-trigger memory for reset and enough post-trigger memory for the
   four validation reads.
3. Trigger on the first assertion of DS1230 `/CS` or U18 `/CS` while the
   address bus is `0xFDFC..0xFDFF`. If neither asserts, trigger on the CPU
   `RD`/`PSEN` event and retain the decode net identified by continuity.
4. Power up and capture one complete boot/checksum window only. Do not press
   buttons, connect a host, transmit serial data, or repeat captures until the
   first wiring is reviewed.
5. Power down before removing probes.

## Decode worksheet

For each `MOVX` read, record the address, CPU control assertion, DS1230 `/CS`
state, DS1230 `/OE`, U18 `/CS`, U18 `/OE`, and any bank-control value:

| Expected CPU address | U17 instruction | Device selected | Data optional |
|---|---:|---|---|
| `FDFE` | `0x0296` | DS1230 or U18 or other | optional |
| `FDFF` | `0x0299` | DS1230 or U18 or other | optional |
| `FDFC` | `0x02A3` | DS1230 or U18 or other | optional |
| `FDFD` | `0x02AA` | DS1230 or U18 or other | optional |
| `8000..FDFC` | `0x038E` loop | device selected during checksum | optional |
| `FDFE` | `0x02E8` | DS1230 or U18 or other | optional |
| `FDFF` | `0x02EB` | DS1230 or U18 or other | optional |

Interpretation:

- Same DS1230 `/CS` assertion for all reads supports, but does not by itself
  prove, a linear DS1230 XDATA mapping.
- U18 selected for the `MOVX` reads while DS1230 is selected for `PSEN` or
  another phase supports separate CODE/XDATA decode.
- A bank-control transition between the marker and checksum reads supports a
  banked decode hypothesis.
- No `/CS` assertion or overlapping `/OE` behavior means the capture must be
  repeated with the continuity-identified decode net; do not guess from data.

The existing static instruction table and independent calculator are in
`U17_CHECKSUM_INSTRUCTION_TABLE.md` and
`u17_checksum_independent.py`. They predict `FDD7` for the candidate under a
linear file-offset model, but the two physical failures mean that prediction
must not be treated as hardware fact.
