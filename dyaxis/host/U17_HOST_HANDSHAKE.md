# U17 Macintosh-host handshake boundary

Scope: U17 V1.06 only. U3, U7, FPGA configuration and general rear-port
analysis are out of scope here.

## Strongest waiting-state evidence

After reset and local diagnostics, `jump_30A7` initializes an external service
sequence through `XDATA 0xFFE1`, then `jump_30AA` waits on external status:

1. `0xFFE1.0` clear: loop through `jump_3253` and return to the wait loop.
2. `0xFFE1.0` set: read one service byte from `0xFFE3` into internal `0xA5`.
3. Dispatch by internal state byte `0xA8` at `0x30C3`.
4. State transitions return to `0x3253`, which handles timeout/status bits and
   returns to `0x30AA`.

This is the strongest ROM evidence for “waiting for host/service input”. It is
not proof that `FFE1/FFE3` are the Macintosh wire registers: they are external
XDATA service addresses behind the board’s decode/peripheral layer.

## External CODE versus XDATA

The U17 image contains no body for `CODE` calls `0xFE00–0xFE6F` or interrupt
handlers `0xFEC1`, `0xFED1`, `0xFEED`. These are calls into a separate code
address space/window, not missing bytes inside the U17 32 KiB image. The
confirmed external XDATA service registers include:

| Address | Evidence | Interpretation |
|---|---|---|
| `0xFFE1` | `0x30AA`, `0x30C3`, `0x3332`, `0x3348` | service status/control and command staging |
| `0xFFE3` | `0x30C3`, `0x327E` | one-byte service data/status register |
| `0xFDFE–0xFDFF` | `0x0293`, `0x02A1`, `0x02CD`, `0x03BE` | external RAM checksum/signature |
| `0xFDFC–0xFDFD` | `0x02A1` | external RAM validity/signature |
| `0x8000–0xFDFD` | `0x03A4`, `0x037C`, `0x321C` | external RAM/program window |

The U17 serial ISR at `0x3416` only reads `XDATA 0xFED0`, calls external
`CODE 0xFED1`, and returns with `RETI`. It does not program a Z85230 channel,
read SBUF, or expose a wire parser in the U17 ROM.

## Z85230 conclusion

U17 does not contain instruction-level Z85230 initialization or either-channel
register programming. The external CODE service layer must own that work, or
the Z85230 is behind another service processor/FPGA interface. Therefore:

- channel assignment is unresolved;
- RX/TX interrupt entry is only proven at the U17 shim (`0x3416`), not the
  Z85230 register handler;
- no U17-derived wire baud is proven.

The board evidence gives a candidate 3.672 MHz Z85230-area crystal, but that is
not enough to derive an external UART baud. Do not use it as a probe setting.

## State transitions and download exclusion

The one-byte service value at `0xFFE3` is dispatched by state `0xA8`:

| Internal state | Handler | ROM-supported effect | First-probe status |
|---:|---|---|---|
| `1` | `0x3109` | copy byte to `0xA2`, increment state | unknown host phase |
| `2` | `0x3115` | accepts data values `1` or `6`, or resets/changes state | unknown host phase |
| `0x28` | `0x3176 → 0x31C1` | receives block bytes and computes external-RAM address | EXCLUDE: download/write |
| `0x2B` | `0x321C` | writes received byte to external RAM via `MOVX` | EXCLUDE: memory write |
| `0x63` | `0x3246` | decrements a transfer counter | EXCLUDE: transfer state |
| `0xD8` | `0x30EE` | accepts `0xFFE3==2`, arms `0x017B/0x017A` | unknown service phase |
| other | `0x3253` | returns to wait/status loop | no accepted transition proven |

`0x30EE` therefore proves a local sequence requiring a received service byte
`2`, but not the Macintosh packet containing it. `0x3176/0x31C1` proves the
download path and is explicitly excluded from active testing.

## Ranked candidate first-host packets

No exact wire packet is recoverable from U17 alone. The candidates below are
state predicates, not invented packets:

| Rank | Candidate | Wire sequence | Expected state/effect | Confidence | Risk |
|---:|---|---|---|---|---|
| 1 | status/query | unknown prefix/address/command/length/checksum; service byte unknown | should produce a non-writing reply/status and advance no download state | low | lowest conceptually, but not transmittable yet |
| 2 | phase-1 byte | unknown packet whose service byte is `01` | enters state `1`, stores byte in `0xA2` | low | unknown; do not transmit |
| 3 | phase-2 byte | unknown packet whose service byte is `02` | enters state `2`; subsequent values `01`/`06` branch | low | unknown; do not transmit |
| — | download/launch | includes state `0x28`, `0x2B`, `0x63` paths | writes/validates external RAM or launches at `0x8000` | high as ROM path, not packet | prohibited |

No length, address/unit ID, checksum, retry packet, or exact response bytes are
proven. The safest active candidate is therefore **none** until a passive
capture identifies the external service framing.

## Capture and probe tools

The tool supports arbitrary baud values where the serial adapter/OS supports
them, records timestamped RX/TX binary records, and never retries. Current
built-in candidates intentionally contain no wire bytes, so probe mode refuses
all of them.

Receive-only capture command:

```sh
python3 dyaxis/host/u17_host_tool.py capture \
  --device /dev/cu.YOUR_RS422_ADAPTER \
  --baud 10416.6667 \
  --duration 30 \
  --output /tmp/u17-standalone.u17cap
```

The `10416.6667` value is only an example adapter setting, not a proven U17
baud. Repeat at a measured/observed rate after passive timing analysis.

Active command template — **DO NOT RUN until connector wiring, transceiver
voltage, direction and differential termination are verified, and a packet is
recovered from passive capture**:

```sh
python3 dyaxis/host/u17_host_tool.py probe \
  --device /dev/cu.YOUR_RS422_ADAPTER \
  --baud YOUR_MEASURED_BAUD \
  --candidate wait-status-query \
  --transmit \
  --output /tmp/u17-one-shot.u17cap
```

At present this command safely refuses because `wait-status-query` has no
resolved wire bytes. It cannot transmit an invented packet.

## Macintosh Mini-DIN-8 wiring boundary

The following is the common Macintosh Mini-DIN-8 RS-422 convention, documented
separately from the Dyaxis port assignment. It is not proven for this unit:

| Pin | Common Macintosh signal | Receive-only use |
|---:|---|---|
| 1 | HSKo | leave open |
| 2 | HSKi | leave open |
| 3 | TXD− | differential pair member; observe only |
| 4 | GND | reference only after voltage/ground check |
| 5 | RXD− | differential pair member; observe only |
| 6 | TXD+ | differential pair member; observe only |
| 7 | GPi | leave open |
| 8 | RXD+ | differential pair member; observe only |

Receive-only means connect a high-impedance differential receiver to one pair
at a time, never connect its driver output, and do not assume Dyaxis connector
channel or polarity matches the Macintosh convention. Transmit wiring is a
separate future step: only after pinout, direction, voltage and termination are
measured should a differential driver be connected to pins 3/6 or 5/8.
