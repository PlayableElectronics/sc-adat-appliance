# U17 uCsim emulation harness

This harness uses the open-source SDCC uCsim 8051 core without modifying the
core. The selected package is Debian `sdcc-ucsim 4.5.0+dfsg-1`, containing
uCsim `0.8.15`; the package is installed in the pinned Debian 13-slim image
`sha256:a99cfc517144bc59b1978475ec53b46ecabec7e43635402ee5b77cc54cd1b20a`.
uCsim is GPL-licensed; the repository adds only the integration layer and
fixture commands.

## Reproduction evidence

Run the retained smoke and reset-entry checks:

```sh
./dyaxis/analysis/test_u17_ucsim_integration.sh
```

The harness builds a bounded synthetic fixture and a U17 CODE image, executes
through the pinned uCsim container, and records only compact stop/state
evidence. No hardware device or serial port is opened. The former broad
CODE/XDATA matrix and its generated report were removed because they did not
constitute full hardware emulation evidence.

## Driver validation and execution boundary

The driver is exercised through the same Docker image, command-file
mechanism, PTY console, explicit stop-event parser, and `state` query used by
the real ROM:

```sh
./dyaxis/analysis/test_u17_ucsim_integration.sh
```

The synthetic fixture executes `LJMP 0003; MOV A,#42; SJMP $`, stops on an
explicit breakpoint at `0x0005`, reports `ACC=0x42`, `PC=0x0005`, and reports
`Inst=3`. The real U17 fixture reaches an explicit breakpoint at reset-entry
`0x2F6F` after two instructions, with the queried CPU state also at `0x2F6F`.
Breakpoint-definition/disassembly text is never treated as a hit.

The execution request is `step 200000`, so instruction work is bounded. A
short wall-clock guard only prevents a broken console process from hanging the
test. The runner reports the explicit stop PC, queried state PC, instruction
count, register snapshot, and compact trace excerpt.

The U17 check deliberately stops at reset-entry. It therefore proves reset
execution only; it does not claim checksum, display, launch, or application
execution.

The earlier offline arithmetic model reproduced the established contradiction:

| Mapping | Projection |
|---|---|
| candidate CODE + candidate XDATA | Checksum Good |
| candidate CODE + original XDATA | Checksum Failed |
| candidate CODE + zero/U18-style XDATA | Checksum Failed |
| candidate CODE + `0xFF` default XDATA | Checksum Failed |
| original CODE + candidate XDATA | Checksum Good |

Under the checksum model, the exact bytes required at the four validation
addresses are `AA 55` at `FDFC/FDFD` and the complemented sum at `FDFE/FDFF`.
For the candidate image that is `AA 55 FD D7`; for an all-zero XDATA fixture
with `AA` at `FDFC`, it is `AA 55 FF 55`. These are model requirements only.

No CODE/XDATA arrangement is promoted as physically established. Unknown
FPGA, PAL and Z85230 interactions are not fabricated as successful responses.
