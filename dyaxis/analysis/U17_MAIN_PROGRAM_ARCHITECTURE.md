# U17 V1.06 main-program architecture

Scope: the verified Studer-Editech U17 AM27C256 image only. This report
incorporates the new board trace evidence that U17 directly supplies the
P80C552 code bus, the small `PALC22V10L-25PC` programmable-logic device
communicates with the XC3030, and the FPGA scans encoders and other console
controls. “PIC” is retained only as the owner’s shorthand for this small
programmable IC; it is not a Microchip PIC microcontroller. U3, U7 and the
Macintosh protocol remain separate evidence domains.

## Evidence status

Confirmed from ROM: reset/startup control flow, XDATA addresses and access
directions, state transitions, interrupt shim targets, external-memory writes,
and the bytes written to the service ports. Strong architectural inference:
U17 is the system leader and `FFE1/FFE3` is a mailbox or service-register
window behind FPGA/PAL glue. Not proven: the exact PAL PCB reference, the
electrical decode of the window, or whether any window is directly visible on
the Macintosh RS-422 interface.

## Reset-to-wait control flow

```text
reset 0000 -> 2F6F
  clear internal RAM 00..FF
  clear XDATA 0000..7FFF
  clear XDATA FE00..FEFF
  SP = CF; apply table-driven init at 2FD2 from ROM table 2211
        |
        v
startup 01E0
  disable interrupts
  FE00 external CODE service; delay 33D8; FE21; 1440 startup/status test
  FE24; FE3F; FE42; 034D; write FEEE=32, FEEF=C9
  enable EA; configure Timer-2/capture at 032F
  test XDATA 0035, P5 and checksum/NVRAM values
  FE06 message services emit boot/checksum/master-reset text
        |
        v
30A7 -> 3348 local-service initialization -> 30AA main service loop
        |
        +-- FFE1.0 clear -> 3253 timeout/status path -> 30AA
        +-- FFE1.0 set -> A5 = FFE3 -> dispatch by A8 at 30C3
        +-- A8=01 -> A2=A5; A8++
        +-- A8=02 -> accept A5=01 or 06; initialize/validate next phase
        +-- A8=D8 -> accept A5=02; arm 017B/017A and advance
        +-- A8=28/2B/63 -> transfer state; external-RAM write path
        +-- other -> return to 3253/30AA
```

The wait loop is therefore a real U17 main application loop, but its input is
an external service indication. The ROM does not prove that the service byte is
a wire byte received from the Macintosh.

## Startup and service routines

`01E0` is the central startup routine. `FE06` is called repeatedly with
register tuples that select strings/messages; because its body is outside the
EPROM, the ROM proves message selection but not the final display bus. This is
consistent with U17 leading display/status services through the FPGA/PAL or an
external peripheral window.

`1440` writes `FFF1=F0`, delays, writes `FFF1=47`, then reads `FFF0`. A read of
`FFF0=05` returns local result `1`; `FFF0=0A` returns result `2`; all other
values return `0`. This is a startup peripheral-identification/status exchange,
not a Macintosh packet parser.

`3348` first performs the `3332` service handshake, then writes the fixed byte
sequence below to `FFE1`:

```text
0B 50 0E 01 0C 01 0D 00 04 C4 03 C1 05 6A 0F 00
10 10 01 00 09 21
```

These are U17-to-external-service writes. Their register/command meaning is
not assigned without observing the decoded bus or the PAL/FPGA side.

`3332` reads the current `FFE1` value, writes `09`, then `C0` and derived
bitwise values. It behaves like service-register acknowledge/initialization
logic, not a portable host-frame encoder.

## Service-value hypothesis

The values `01`, `02`, `06` and `FF` do not share one unconditional meaning;
their effects depend on U17 state `A8`:

| Service value | Required U17 state | ROM effect | Confidence |
|---:|---:|---|---|
| `01` | `A8=02` | branch at 3138; clear/finish phase, or call 32A9 when A2 is zero | Confirmed local effect |
| `02` | `A8=D8` | set XDATA `017B=1`, `017A=32`, increment A8 | Confirmed local effect |
| `06` | `A8=02` | if A2 is in `01..80`, load A6/A7 and enter transfer state `28` | Confirmed local effect |
| `FF` | `A8=28` | terminal transfer value; may complete validation and call 328A | Confirmed local effect |

The `06`/`FF` paths are associated with the external-RAM/download machinery
and must not be used as control-scan commands. The values could be PAL/FPGA
service events, but that remains a hypothesis until a passive bus or wire
capture correlates them with hardware activity.

## Interfaces kept separate

| Interface | U17 evidence | Current interpretation |
|---|---|---|
| P80C552 ↔ PAL/FPGA | `FFE1/FFE3`, `FFF0/FFF1`, `FEEE/FFEF`, external CODE/XDATA shims | local mailbox/status/service layer; strongest new architecture hypothesis |
| P80C552 ↔ subordinate controllers | external RAM window `8000..FDFD`, transfer states `28/2B/63`, FE06 services | boot/launch and board-service paths; exact subordinate endpoint unresolved |
| P80C552/Z85230 ↔ Macintosh host | serial ISR `3416` reads `FED0`, calls `FED1`; no direct SIO0 setup | separate external serial service path; no host framing proven |

No U3 `FD/FE` meaning or U7 UART constant is imported into the U17 mailbox
interpretation.

## PAL/FPGA identity boundary

Repository photos clearly identify `XILINX XC3030TM-70 PC68C` and
`PALC22V10L-25PC` (`9353 000020`). In particular,
`photo/image-1789743641546.jpg` shows the referenced small device clearly:
`PALC22V10L-25PC`, second line `9353 000020`. The PCB reference is not legible
in that image. The 2676/2677/2684 close-ups show the U3/P80C552 board, FPGA
and PAL area, while 2667/2668 show the
`Z85230VSC` and 3.672 MHz oscillator. The photographed `LH5163-10L SHARP`
device is SRAM on the Uptown board, not an identified PIC.

The referenced small device is therefore identified as a PALC22V10-family
programmable-logic device, not a CPU with ordinary executable program memory.
Its nonvolatile programmable logic contents and any device security/protection
state are not preserved in the repository. Do not remove, erase, program or
attempt a programmer read until the exact supported device definition,
orientation and preservation procedure are established.

The physical trace evidence makes this division plausible: the PAL can be
small configuration/scan-service logic communicating with the FPGA, while the
P80C552 remains the leader that accesses the decoded service window. It does
not prove that every `FFE1/FFE3` transaction reaches the PAL; FPGA/PAL
registers or another peripheral remain possible.

## Remaining passive measurements

1. With power off, photograph the PAL square-on so its PCB reference and
   surrounding trace destinations are readable; no removal is required.
2. Capture the P80C552 external bus or use high-impedance probes on the
   decoded `FFE1`, `FFE3`, `FFF0/FFF1` and interrupt-service strobes during
   power-up. This distinguishes PAL/FPGA mailbox logic from other registers.
3. Correlate one `FFE3` service event with the FPGA scan activity and one
   display/status update. Do not transmit on RS-422 during this step.
4. Separately identify which external service window the Z85230 interrupt
   shims expose; do not infer Macintosh framing from the local mailbox.
