# Three-controller architecture and standalone startup

## Responsibility map

| Board/device | Firmware/storage | Proven responsibility | Open boundary |
|---|---|---|---|
| Studer CPU board, assembly `41.005.430.01`, U17 | AMD AM27C256 U17, public SHA `22aa…e0dd` | Strongest system-leader candidate: main boot and supervisory firmware, checksum/NVRAM tests, FPGA/peripheral service initialization, main wait/event state machine, executable-RAM launch path | Exact mailbox decode, display service endpoint, Z85230/rear-port ownership; entire executable system not yet proven inside U17 |
| Same Edit Panel CPU board, U3 | AMD AM27C256 U3, public SHA `7de44a…f22b3` | SIO0 byte rings, Timer-0 panel scan, P4/P5 multiplex I/O, event queue, output update | Physical connector and exact display/LED/encoder assignments |
| Uptown Automation fader board, U7 | ST M27C128, public SHA `a29a17…eb0c3` | PWM motor paths, ADC/fader feedback, P1/P4 scan/output, local SIO0 diagnostics | Board-link framing, transceiver and rear-port relationship |
| Main-board programmable logic beside FPGA | `PALC22V10L-25PC`, `9353 000020`; PCB reference not legible | Current evidence places it in address-decoding, control, timing or glue logic around the XC3030 | Exact nets, programmed equations and any stateful role remain unknown |
| Main-board XC3030/PAL | Volatile XC3030 plus `PALC22V10L-25PC` glue | FPGA scans encoders/console controls; PAL/FPGA likely decode U17 service window and provide timing/glue | Configuration source, exact nets and function |
| Main-board Z85230-family device | Volatile dual-channel serial controller | Plausible dual serial transport/service endpoint | Full suffix, channel wiring and port mapping |

## Standalone startup interpretation

The observed no-host behavior—boot text, fader movement, LEDs and displays—does
not require a host-download assumption. The strongest evidence-supported
sequence is:

1. U17 reset/startup initializes board services and emits boot/checksum text
   through external service calls around `0xFE06`; its `FFE1/FFE3` loop is now
   more plausibly a local FPGA/PAL mailbox than a Macintosh-host parser.
2. U3 runs its own reset path, starts SIO0 and Timer 0, scans P5 through P4,
   and maintains output buffers even without a host.
3. U7 starts PWM/ADC and per-channel feedback loops, providing fader motion
   and local control-board output.
4. The XC3030 probably implements scanning/interface logic, while the
   PALC22V10 likely supplies glue/decode/control logic around it. Both
   assignments remain partly inferential; XC3030/PAL/Z85230 hardware mediates distinct local and
   serial-service paths.
5. The surface reaches a local waiting/diagnostic state.

The first and third steps are directly supported by U17/U7 code. U3’s timer
scan/output behavior supports the second. The exact path by which U17 boot text
reaches the physical display, and whether U3 or FPGA logic performs the final
display serialization, remains unresolved.

## Serial comparison

U3 has a direct SIO0 ISR and two small internal RAM rings. U7 has direct SIO0
initialization and diagnostic transmit code. U17 has no reachable direct SIO0
register setup; its ISR is an external service shim. This is consistent with
three different communication roles, not one shared MCU packet parser.

No static result proves that the rear `(RS422) SERIAL 1/2` connectors carry
U3, U7, U17, Z85230, or more than one of those paths. The U17 `FFE1/FFE3`
mailbox must not be treated as the Macintosh protocol. The rear-port
hypothesis must remain passive until transceivers and pairs are identified.

The detailed U17 reconstruction and literal high-address map are in
`U17_MAIN_PROGRAM_ARCHITECTURE.md` and `U17_HIGH_ADDRESS_MAILBOX.md`.

## Minimum Linux boundary

Keep the future adapter as:

```text
existing controller serial service
    <-> normalized buttons/encoders/faders, LEDs and display state
    <-> OSC mixer API
```

Do not implement a transmitter or replacement 8051 application until one
repeatable passive event and its reply path are identified.
