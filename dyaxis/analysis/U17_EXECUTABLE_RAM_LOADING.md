# U17 executable-RAM loading verdict

Date: 2026-09-18. Scope: the verified public U17 ROM only.

## Verdict

**Executable-RAM loading is confirmed at the instruction-path level.** The
ROM contains a reachable receive-to-external-XDATA write path, a validation
path covering the external application area, and a transfer of control to
external code at `0x8000`. The exact host wire framing, transport register
semantics and all metadata field meanings remain unresolved; no transmitting
loader is implemented.

## Evidence chain

The following are valid instructions in the control-flow-aware disassembly
`generated/u17/u17.reachable.asm`:

1. **Receive/service input:** `jump_30AA` tests external `XDATA 0xFFE1` bit 0,
   then `jump_30C3` reads one byte from `XDATA 0xFFE3` into internal RAM byte
   `0xA5`. This is the strongest available receive indication; `0xFFE1` and
   `0xFFE3` are external service registers/windows, not named MCU UART SFRs.
2. **External-RAM write:** the state path reaches `jump_321C`. It takes the
   received byte from `0xA5`, loads a DPTR from `0x9E:0x9F`, and executes
   `MOVX @DPTR,A`. `jump_31C1` forms that pointer as `0x8000 + (block * 0x80)`
   for block values below `0xFC`; the surrounding state/counter logic advances
   the received data through the external RAM window.
3. **Clear and checksum:** `jump_03A4` explicitly clears external XDATA in
   the half-open range `[0x8000,0xFDFD)`, i.e. through `0xFDFC`.
   `jump_037C` sums that same range and returns the
   complemented 16-bit result in `R6:R7`. This is not a raw byte-pattern
   inference.
4. **Validation gate:** the startup code first checks `0xFDFE/0xFDFF == AA55`
   and then `0xFDFC/0xFDFD == AA55`. Any failure branches to `jump_02CD`,
   which calls `jump_037C`, reads `0xFDFE/0xFDFF` again, and compares those
   same bytes against the complemented sum. The dual marker/checksum use is
   unresolved; the prior image contract is falsified by the hardware test.
5. **Transfer:** `jump_328A` disables interrupts, quiesces Timer 2/PWM state,
   and executes `LCALL 0x8000`. The external application therefore enters as
   a subroutine, not as a reset vector or `LJMP`.

## Recovered application ABI

Confirmed ABI surface:

- Load base: `0x8000` in external code/XDATA address space.
- Checksum input span: `0x8000`–`0xFDFC`, inclusive; the emulator confirms
  the half-open file slice `image[:0x7DFD]`. Startup separately requires
  `AA55` at both `FDFE/FDFF` and `FDFC/FDFD` before the failure/checksum path.
  The clear/checksum endpoint is exclusive at `0xFDFD`.
- Entry: `LCALL 0x8000`; application must eventually use `RET` to return to
  U17 `jump_328A`. A reset, `RETI`, or non-returning transfer is not supported
  by this observed call site.
- Entry conditions: interrupts disabled; `P4.4` set; `PWM0` cleared; PSW.4
  and PSW.3 cleared; Timer 2 control/interrupt state cleared; existing stack
  remains in effect. Other register and peripheral guarantees are unknown.
- Download granularity candidate: `0x80`-byte blocks, because `jump_31C1`
  multiplies a received block/index value by `0x80` and adds it to `0x8000`.
  The exact block header, byte count, ordering and completion marker require
  capture.
- Checksum: a complemented 16-bit sum over the validation span is confirmed;
  exact byte order and the roles of all four metadata bytes remain unresolved.

## Minimal replacement application design

The first replacement application should be a diagnostic image that:

1. enters at `0x8000`;
2. preserves the observed interrupt-disabled/quiesced entry assumptions;
3. performs no panel or RS-422 writes initially;
4. records a deterministic alive/status value in an agreed external register
   only after that register is identified by bus tracing; and
5. returns with `RET` to test the U17 launch/return contract.

Do not define a complete panel ABI, OSC mapping, or host packet encoder until a
passive capture identifies the external service registers and wire framing.

## Remaining proof and safety boundary

The executable-RAM mechanism is proven in ROM logic, but successful delivery
of a real application still requires a passive capture to recover the receive
transport and metadata bytes. The host-loader skeleton therefore constructs a
validated, non-transmitting load plan only; it cannot open a serial device or
send bytes.
