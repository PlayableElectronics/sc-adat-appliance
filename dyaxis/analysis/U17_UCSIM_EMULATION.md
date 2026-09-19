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

## Result and limitation

The A–H matrix was run with a five-second bound per case. uCsim loaded the
fixtures but did not reach a terminal checksum breakpoint; every case stopped
in the startup/service path timeout. This is an emulator integration result,
not evidence that the physical board waits for the same reason. The report's
`static_path_projection` field is the independent known checksum model and is
explicitly not instruction-execution evidence.

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

Because complete uCsim execution did not reach the branch, no CODE/XDATA
arrangement is promoted as physically established. The candidate-plus-
independent-XDATA cases are the leading decode hypotheses, consistent with
the existing PAL/FPGA/U18 architecture, but require the targeted chip-select
measurement in `U17_MEMORY_DECODE_MEASUREMENT_PLAN.md`.

The current runner intentionally does not claim executed instruction counts,
FE06 display events, `0x328A`, or `LCALL 0x8000` when uCsim times out. Unknown
FPGA, PAL and Z85230 interactions are not fabricated as successful responses.
