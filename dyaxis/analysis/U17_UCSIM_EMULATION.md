# U17 uCsim emulation harness

This harness uses the open-source SDCC uCsim 8051 core without modifying the
core. The selected package is Debian `sdcc-ucsim 4.5.0+dfsg-1`, containing
uCsim `0.8.15`; the package is installed in the pinned Debian 13-slim image
`sha256:a99cfc517144bc59b1978475ec53b46ecabec7e43635402ee5b77cc54cd1b20a`.
uCsim is GPL-licensed; the repository adds only the integration layer and
fixture commands.

## Reproduction

Build and run the one-container matrix:

```sh
./dyaxis/analysis/run_u17_ucsim.sh --experiment all \
  --output /work/dyaxis/analysis/generated/u17/u17-ucsim-experiments.json
```

The runner creates a 64 KiB Intel-HEX CODE image: U17 EPROM at `0000..7FFF`
and the selected external image at `8000..FFFF`. It independently initializes
uCsim XRAM at `8000..FFFF`, sets terminal fetch breakpoints, and retains only a
compact excerpt and SHA-256 of the optional complete trace. Complete traces
belong under ignored `.local/` storage and are never tracked.

The harness supports original, candidate, zeroed/U18-style, mutable-original,
and `0xFF` diagnostic XDATA fixtures. It records the checksum span, supplied
`FDFC..FDFF` bytes, terminal path, launch breakpoints and unknown peripheral
behavior. No hardware device or serial port is opened.

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

The current matrix deliberately stops at reset-entry. It therefore proves
reset execution only; it does not claim checksum, display, launch, or
application execution. The report's `static_path_projection` field remains a
separate checksum-model calculation and is never promoted to an executed
path.

The projection reproduces the established contradiction:

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

No CODE/XDATA arrangement is promoted as physically established by this
matrix. The candidate-plus-independent-XDATA cases remain decode hypotheses,
consistent with the existing PAL/FPGA/U18 architecture, and require the
targeted chip-select measurement in `U17_MEMORY_DECODE_MEASUREMENT_PLAN.md`.
Unknown FPGA, PAL and Z85230 interactions are not fabricated as successful
responses. Since no current matrix run reached the checksum or launch
breakpoints, those paths are intentionally absent from `display_strings` and
the launch fields.
