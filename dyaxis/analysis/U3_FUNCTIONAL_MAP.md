# U3 P80C552 functional map

Method: P80C552-aware `disasm51` with reset plus explicit interrupt/vector
entry points. Addresses below are valid instruction boundaries in
`generated/u3/u3.vectors.asm`. “Strong candidate” means the register and loop
behavior support the role; it does not assign a physical connector by itself.

## Reset, timers and serial interrupt

- Reset `0x0000` is `LJMP 0x00F7`. `0x00F7–0x014C` clears internal RAM,
  establishes `SP=0xC7`, initializes pointers, enables Timer 0, SIO0 and
  global interrupts, and sets `TH0/TL0=DA00`, `TH1=FD`.
- The Timer 0 vector bytes `41 62` at `0x000B` decode as an 8051 `AJMP
  0x0262`. `0x0262–0x028D` is a timer service: it decrements byte `0x63`,
  turns `PWM0` off when the count expires, calls the output/input routines,
  reloads Timer 0 and returns with `RETI`.
- The SIO0 vector at `0x0023` begins an inline ISR. It clears `PWM0`, reloads
  `0x63=0x32`, tests `S0CON.0`, and at `0x0031–0x004E` stores received
  `S0BUF` bytes into `0x90–0x9F`, wrapping at `0xA0`, then clears the serial
  condition and returns with `RETI`.
- `0x0157–0x018A` consumes the RX ring. `0x018E–0x01A8` consumes the
  controller-generated TX/event ring. `0x01CE` writes selected bytes to
  `S0BUF`.

At 12 MHz, Timer 0 reload `0xDA00` is approximately 9.728 ms in ordinary
12-clock mode; `0x32` therefore represents approximately 486 ms. This is a
timing calculation, not a measured watchdog period.

## Panel input scan and event encoding

`0x02D0–0x02EE` drives P4 with `0xFE` rotated through eight positions and
reads P5 into `0x49–0x50`; it then drives P4=`0xFF`, toggles P1.0 and reads a
ninth P5 sample into `0x51`. `0x02F0–0x03D7` compares the nine current bytes
with the previous image at `0x40–0x48`.

For every changed bit, the routine forms an event group base of `0x80`,
`0x90`, `0xA0`, …, `0xF0`, adds a scan-position index derived from `9-R3`,
and queues a second byte with `0x03DA`. A sign/polarity bit is taken from the
previous/current state bookkeeping at `0x21.x`. This is confirmed raw switch/
input-change encoding; which groups are buttons, encoders or other panel
inputs remains unresolved.

There is no proven quadrature phase accumulator or explicit wheel decoder in
the reachable U3 paths. A wheel/encoder may be represented as two raw P5 bits,
but that requires a capture or board trace.

## Output, LED and display candidates

`0x029F–0x02CE` is the output-side multiplexer. If the P4 test at `0x028E`
does not pass, `0x02A5` writes a selector value and then eight bytes from
`0x30–0x37` and eight bytes from `0x38–0x3F` to P4 while changing P3 strobes.
This is strong evidence for a multiplexed panel-output bus. It could drive
LEDs, display segments/characters, or an intermediate latch; the ROM does not
name the physical destination.

The U3 image contains no direct display-controller SFR, no display strings
referenced by reachable code, and no separate LED register. Therefore:

- display initialization/write: partial, with `0x02A5` the best candidate;
- LED output: partial, with `0x02A5` and `0x30–0x3F` the best candidates;
- exact display protocol and LED bit assignment: unresolved.

## RAM and external-device map

| Range/register | Use supported by code |
|---|---|
| `0x30–0x3F` | two eight-byte output/multiplex buffers |
| `0x40–0x48` | previous nine-byte P5 scan image |
| `0x49–0x51` | current nine-byte P5 scan image |
| `0x5B` | temporary encoded event value |
| `0x5D/0x5E/0x5F` | TX/event read pointer, write pointer, count |
| `0x60/0x61/0x62` | RX read pointer, write pointer, count |
| `0x63` | serial-to-PWM timeout/reload counter |
| `0x80–0x8F` | TX/event ring |
| `0x90–0x9F` | RX ring |
| `0xA0–0xBF` | 32-byte state/output image indexed by `0x03F3` |
| P1.0, P1.3, P3, P4, P5 | panel strobes, multiplex bus and input port |

No reachable `MOVX` instruction occurs in the U3 vector pass. U3 therefore
provides no instruction-level evidence for an external XDATA device or address
range. The indirect table at `0x0411` contains targets above the visible 32 KiB
image; those targets are not assigned and may be data, banked code, or an
unmapped/other-memory convention. They must not be called confirmed devices.
