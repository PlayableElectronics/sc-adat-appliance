# Dedicated Nano passive Dyaxis RS-422 capture

This setup uses a second Arduino Nano. The existing ADB Nano and its wiring
remain unchanged. The Nano records only logic transitions from the YL-128
receiver output; it never transmits to the Dyaxis.

## Firmware and stream

Flash `dyaxis/arduino/DyaxisRS422EdgeCapture/DyaxisRS422EdgeCapture.ino` to
the dedicated Nano. The sketch uses Timer1 at 2 MHz (0.5 microsecond ticks),
INT0 on D2, and a bounded 96-entry ring buffer. The interrupt stores only a
timestamp and level. Overflow frames carry cumulative and newly lost-event
counters; they are capture-quality failures, not ignorable status.

The USB stream begins with the `DYAXEDG1` header and explicit READY, START,
EDGE, OVERFLOW and STOP markers. The raw `.dyaxedge` file is preserved before
offline decoding. D0/D1 are used only by the USB serial transport and are not
connected to the captured signal.

## Exact receive-only wiring

Use a YL-128/MAX490 receiver module configured only as a receiver:

| Connection | Purpose |
|---|---|
| Nano 5V → YL-128 VCC | module power |
| Nano GND → YL-128 GND | logic reference |
| YL-128 RXD → Nano D2 | captured TTL input |
| YL-128 TXD | disconnected |
| YL-128 transmitter differential pair | disconnected |
| YL-128 receiver pair | connect only to Dyaxis TX−/TX+ |
| Nano D0/D1 | no connection to Dyaxis or YL-128 signal |

Confirm module labeling and voltage levels before powering it. Do not connect
the module’s driver output or its differential transmitter pair. Dyaxis
connector polarity and channel assignment remain hardware facts to verify.

## First recording

Prepare the Mac capture process with the Dyaxis powered off. The host sends
`R` only to the Nano over USB, then records for 16 seconds. The planned event
timeline is: power on at 0 seconds, 10 seconds idle, press and release one
named button once, 5 seconds idle, then send `S`. The host writes a Markdown
timeline beside the raw binary; fill in observed wall-clock/video details
afterward. Capture is not hardware-validated until a real recording has been
made and decoded.

```sh
python3 dyaxis/host/nano_edge_capture.py capture \
  --device /dev/cu.usbserial-DEDICATED-NANO \
  --duration 16 --button-name M1 \
  --output captures/dyaxis-poweron-M1.dyaxedge \
  --timeline captures/dyaxis-poweron-M1.timeline.md
```

The `R` and `S` bytes are USB control commands to the Nano; they are not
Dyaxis or RS-422 transmissions. Start the command, power the console on, and
perform exactly one named button press/release at the 10-second mark.

Decode without inventing packet semantics:

```sh
python3 dyaxis/host/nano_edge_capture.py decode \
  --input captures/dyaxis-poweron-M1.dyaxedge \
  --report captures/dyaxis-poweron-M1.decode.json \
  --bytes-output captures/dyaxis-poweron-M1.bytes.jsonl
```

The decoder estimates bit periods, includes 10416.6667 baud only as a
hypothesis, tries normal and inverted polarity plus common UART data/parity/
stop combinations, and ranks by framing errors and repeatability. It exports
timestamped bytes only; packet meaning remains a later evidence-based step.

## Tests and limitations

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=dyaxis/host \
  python3 -m unittest discover -s dyaxis/host -p 'test_*.py'
```

Tests generate deterministic non-proprietary edge fixtures covering jitter,
inversion, truncation, overflow and the 10416.6667 hypothesis. They do not
claim Nano, YL-128 or Dyaxis electrical validation.
