# U17 application-download protocol reconstruction

This report is intentionally split between ROM-proven service state and the
unrecovered wire protocol. No packet is safe to transmit from this analysis.

## Proven state machine

The path begins at `0x30A7`, which calls `0x3348`, then enters `0x30AA`.
`0x30AA` polls candidate service status `XDATA 0xFFE1`; when bit 0 is set,
`0x30C3` reads one byte from `0xFFE3` into internal RAM `A5` and dispatches on
internal state byte `A8`. The exact service producer and its relationship to
the Macintosh wire are not proven.

```text
30A7/3348
   |
30AA: FFE1.0 == 0? ---- yes ---> 3253 status/timer path ---+
   | no                                                   |
30C3: A5 = FFE3; dispatch by A8                             |
   |                                                        |
   +-- A8=00, A5=02 -> 017B=1, 017A=32, A8=01 ------------+
   +-- A8=01          -> A2=A5, A8=02 ---------------------+
   +-- A8=02,A5=01    -> finish/reset or 32A9 --------------+
   +-- A8=02,A5=06    -> require 1<=A2<=80; A6:A7=0x0BB8;
   |                     A8=28 -----------------------------+
   +-- A8=28,A5!=FF   -> 31C1; block=A5 (<FC),
   |                     DPTR=8000+block*80, A8=29 --------+
   +-- A8=29          -> 321C; write A5 via MOVX, decrement A2;
   |                     repeat, or clear 017B/A8 ----------+
   +-- A8=28,A5=FF    -> decrement A2; if zero -> 328A -----+
   +-- A8=5A          -> 3246 counter/cleanup --------------+
   +-- otherwise      -> 3253 ------------------------------+
```

At `0x328A`, U17 disables interrupts, sets `P4.4`, clears `PWM0`, clears
selected PSW bits and Timer 2 state, calls `0x3332` twice, then executes
`LCALL 0x8000` (`0x32A2`). This is an application launch, not proof of a wire
completion packet.

## State/field evidence table

| Candidate service field | Exact evidence | Proven meaning |
|---|---|---|
| availability | `30B9–30C1`, read `FFE1`, test bit 0 | service byte available |
| service byte | `30C3–30C8`, read `FFE3` into `A5` | one-byte service input |
| state | `30C8–30ED`, internal RAM `A8` | local dispatch state |
| count | `3109`, `314B`, `3176`, `321C`, `3246`, internal `A2` | byte count/remaining transfer count in download path |
| block index | `31C1`, `A5`, reject `A5 >= FC` | 128-byte destination block selector |
| destination | `31C1`, `9E:9F`, `321C` | `0x8000 + block*0x80`, then incremented for payload |
| payload byte | `321C`, `MOVX @DPTR,A` | one received byte written to external XDATA |
| terminal marker candidate | `3176`, `A5 == FF` | terminal transfer value in local state, not proven wire framing |
| launch | `31BA–31B7` and `328A/32A2` | external validation/launch path; exact success branch requires capture/caller context |

The download setup accepts a count in `A2` from 1 through `0x80` at `0x314B`.
The block index is limited to `0x00..0xFB`, yielding a final block base of
`0xFD80`; the transfer routine can write through `0xFDFF`. These are firmware
facts, not a recovered packet length or byte order.

## Received-byte origin

The U17 ROM proves only this chain:

```text
external producer/hardware -> XDATA FFE1 bit 0
                           -> XDATA FFE3 byte
                           -> A5 at 30C3
                           -> A8 state dispatch
```

The serial interrupt vector at `0x0023` enters `0x3416`, reads `XDATA FED0`,
and calls external CODE `0xFED1`. U17 contains no Z85230 register programming,
SBUF access, or wire parser. Therefore the external service layer, mapped
CODE, FPGA/PAL decode, Z85230 handler, or another processor may bridge the
wire to `FFE1/FFE3`; this cannot be selected statically.

## Not recovered from ROM

No valid evidence identifies wire start/end bytes, escaping, CRC/checksum,
sequence numbering, Macintosh unit address, acknowledgement bytes, retry
packets, or timeout values on the wire. `0x017A=0x32` and the timer/status path
at `0x3253` are internal service timing evidence, not a wire timeout in
milliseconds. The Z85230 channel and rear connector remain unresolved; the
candidate board oscillator does not prove a baud rate.

## Minimum passive capture

Capture one standalone power-up with a high-impedance RS-422 receiver on each
candidate receive pair separately, transmitter disconnected, while preserving
timestamps and idle periods. The minimum useful event is: power-on, 10 seconds
idle, one named button press/release, 5 seconds idle. For download-specific
evidence, passively capture a naturally generated service transaction if one
exists; do not initiate a write. Correlate byte timing with `FFE1`/`FFE3` or
Z85230 interrupt activity using a second synchronized logic-analyser channel.

The decode-only mode in `u17_host_tool.py` reports raw RX bytes and a
*candidate service-byte* state simulation. It does not assign wire packet
semantics and never transmits.

```sh
PYTHONPATH=dyaxis/host python3 dyaxis/host/u17_host_tool.py decode \
  --input capture.u17cap --output capture.u17.decode.json
```
