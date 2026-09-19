# Standalone controller startup and local-control ownership

Date: 2026-09-18.

## Confirmed new evidence

With no original Macintosh host connected, the powered controller:

- moves its motorized faders;
- lights LEDs; and
- writes text to its displays.

This proves that meaningful local hardware control is available from the
preserved controller firmware/logic. “Host download required for all
operation” is no longer the default assumption.

## Most-supported architecture

The evidence supports a distributed combination rather than one ROM doing all
work:

| Function | Best current owner | Evidence/status |
|---|---|---|
| Boot, checksum, local diagnostics, launch/handshake | Studer-Editech U17 P80C552 ROM | Confirmed U17 strings and startup path; external services remain partly opaque |
| Fader motor PWM and position feedback | Uptown Automation U7 P80C552 board | Strong: U7 uses PWM0/PWM1, ADCON, timer control, and repeated per-channel loops |
| Button/encoder scan and LED output | U7 P80C552 plus its local I/O/multiplex hardware | Strong candidate: U7 reads/writes P4 while selecting rows with P1 and strobes P3.5 |
| Text/status output | U7 UART/display-service path and/or U17 external display service | U7 has direct S0BUF output and formatted diagnostics; U17 delegates display-like calls externally |
| Address decode and bus glue | XC3030 FPGA + PALC22V10L-25PC | Hardware fact; exact nets/functions require tracing |
| Serial transport | Z85230-family controller and/or P80C552 SIO0 paths | Board-level ownership unresolved; U7 directly initializes SIO0, while U17 serial ISR uses external service registers |

Battery-backed/nonvolatile RAM is present in the U17 diagnostic vocabulary and
external address map, but standalone operation does not require assuming that
it contains the application. U17 visibly performs local initialization and
U7 visibly contains local control loops.

## U17 startup/diagnostic state machine

Confirmed code path and calls:

1. `0x0000 -> 0x2F6F` clears internal RAM and initializes the stack, then
   transfers to `0x01E0`.
2. `0x01E0` disables interrupts, calls external service targets `0xFE00`,
   `0xFE21`, `0xFE24`, `0xFE3F`, `0xFE42`, initializes display/service state,
   and calls local `0x1440` and `0x034D`.
3. `0x1440` writes external service registers `0xFFF1`/`0xFFF0` and returns a
   three-way status used by startup branching.
4. Startup calls external message/display service `0xFE06` with several
   register-parameter tuples, then runs local `0x0DFE` timing/diagnostic work.
5. The path checks external flags and P5 inputs. It can clear the external
   RAM/application span through `0x03A4`, validate it with `0x037C`, and launch
   `LCALL 0x8000` through `0x328A`.
6. The U17 image does not directly show a complete fader/LED/display loop;
   those functions are more strongly represented in U7 and/or external FPGA/
   peripheral services. New trace evidence makes a PALC22V10↔XC3030 scan subsystem
   part of that external service layer. The final waiting state is therefore
   board-level, not assigned to U17 alone; `FFE1/FFE3` is not assumed to be a
   Macintosh-host protocol.

## U7 local hardware candidates

The control-flow-aware U7 pass gives stronger local-control evidence:

- `0x1CA9`: `TMOD=0x20`, `TH1=0xF4`, `PCON.7=1`, `TCON=0x40`, `S0CON=0x52`,
  `S0BUF=0`; direct UART initialization.
- `0x21EA`: direct S0BUF transmit routine, including CR/LF handling and
  XON/XOFF-like input checks.
- `0x0731`, `0x0FEF`, `0x1C83`, `0x1C9C`: PWM0/PWM1 motor-control and timeout/
  safety paths.
- `0x102D`/`0x0664`: ADCON conversion and per-channel feedback processing.
- `0x177E`/`0x17D7`: P4 reads and writes with P1 row selection and P3.5
  strobing; strong button/LED multiplex candidates.
- `0x2276`: formatted diagnostic/status output path; `0x024E` emits the
  literal `reset. ` through `0x21EA`.

With the documented 24 MHz U7 oscillator and `TH1=0xF4`, standard 8051 Timer-1
mode-2 arithmetic gives a nominal 10,416.7 baud when `SMOD=1`; this is a
candidate only until measured on the physical link.
