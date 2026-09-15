# Agent skill and MCP catalog

Research snapshot: 2026-09-15.

## Policy

- Prefer a pinned external installation over vendoring third-party source.
- Record repository URL, exact commit and license before installation.
- Inspect every `SKILL.md`, installer, hook and MCP server before running it.
- Skills and MCP servers are Debian development tools, not appliance runtime.
- A useful skill must require evidence: compile, lint, simulate, render or test.
- Domain advice without a verification path is a reference, not an approved
  workflow.

## SuperCollider

### SuperCollider Pilot — strong candidate

- Repository: https://github.com/Bayern99/supercollider-pilot
- Reviewed commit: `99a817a625590708b8e4228a03cb5757e8232ddd`
- License: ISC
- Provides persistent `sclang`, structured CLI/MCP operations, rendering,
  logging, health state and recovery.
- Intended location: Debian development environment.
- Required evaluation: install with pinned Node dependencies, run its tests,
  execute a minimal patch, perform NRT render, deliberately break/recover the
  session, and confirm it cannot silently claim success.

### sc-designer-upgraded — evaluate

- Repository: https://github.com/thehalleyyoung/sc-designer-upgraded
- Reviewed commit: `7a667b7929705cd3e4756bbd2efd03c792bd2b62`
- Upstream: https://github.com/rheadsh/audiovisual-production-skills
- Provides creative SC authoring plus verification scripts and eval fixtures.
- Licensing warning: its README/UPSTREAM file says MIT, but the reviewed root
  did not contain a standalone `LICENSE` file. Confirm redistribution terms
  before vendoring.
- Required evaluation: silent-output fixtures, syntax failures, multichannel
  channel-count checks, runaway level/NaN protection and headless operation.

## Pure Data and libpd

No convincing general-purpose Pure Data/libpd agent skill was found in the
initial search. Search results were unrelated or project-specific.

Authoritative sources for a future project skill:

- Pure Data: https://github.com/pure-data/pure-data
- libpd: https://github.com/libpd/libpd
- libpd Wiki: https://github.com/libpd/libpd/wiki
- Pure Data documentation: https://pd.iem.sh/

A useful project skill should parse or launch patches headlessly, capture Pd
console errors, verify expected objects/externals, run deterministic audio
fixtures, and understand the project's MicroPython/libpd constraints. We should
build this locally rather than adopt an unverified generic prompt.

## Daisy Seed / libDaisy

### sebasdv/my-skills — reference candidate, not general approval

- Repository: https://github.com/sebasdv/my-skills
- Reviewed commit: `bba7fa7dc48c339bea7d6de8accf7f04fb20389b`
- Contains several project-oriented Daisy/libDaisy/DaisySP skills covering DSP,
  sequencing, SDRAM samples and OLED DMA.
- Limitation: strongly shaped around the author's own hardware/projects.
- License and every selected skill must be reviewed before reuse.

Authoritative sources for our own Daisy skill:

- libDaisy: https://github.com/electro-smith/libDaisy
- DaisySP: https://github.com/electro-smith/DaisySP
- DaisyExamples: https://github.com/electro-smith/DaisyExamples
- Documentation: https://electro-smith.github.io/libDaisy/

Our skill should pin the board/toolchain, stop on the first compiler error,
report FLASH/RAM/SDRAM use, distinguish build from flash success, preserve known
working DSP behaviour, and require an explicit hardware smoke test.

## FPGA and RTL

### hdl-tools/digital-chip-design-agents — strong RTL candidate

- Repository: https://github.com/hdl-tools/digital-chip-design-agents
- Reviewed commit: `d9ec7f93343ecdd7bd7d886ef28563f8c5960308`
- Relevant skill:
  https://github.com/hdl-tools/digital-chip-design-agents/tree/master/plugins/rtl-design/skills/rtl-design
- Covers RTL design/review, linting, simulation, CDC/RDC considerations and
  synthesis readiness using tools including Surelog, sv2v, Icarus and Yosys.
- Required evaluation: license, trigger scope, tool dependencies, small
  synthesizable SystemVerilog fixture and failing-testbench behaviour.

### a5c-ai/babysitter Verilog/SystemVerilog skill — reference candidate

- Repository: https://github.com/a5c-ai/babysitter
- Reviewed commit: `feb68abe397acc14f32b34984975c48fedba2b33`
- Skill:
  https://github.com/a5c-ai/babysitter/tree/main/library/specializations/fpga-programming/skills/verilog-sv-language
- Includes Verible lint/format guidance and a Verilog/SystemVerilog workflow.
- Limitation: the parent repository is very large and brings an orchestration
  framework we probably do not need. Evaluate the isolated skill only.

Authoritative sources for target-specific skills:

- Yosys: https://github.com/YosysHQ/yosys
- nextpnr: https://github.com/YosysHQ/nextpnr
- Project IceStorm: https://github.com/YosysHQ/icestorm
- iCEBreaker examples: https://github.com/icebreaker-fpga/icebreaker-examples
- Xilinx ISE is required for the Spartan-6 Mojo path; keep it isolated in the
  pinned amd64 `mojo-ise` container.

We likely need two local FPGA skills rather than one broad prompt:

1. `ice40-audio-rtl`: iCEBreaker, Yosys/nextpnr/IceStorm, I2S/ADAT DSP,
   simulation and timing-report checks.
2. `mojo-spartan6`: legacy ISE container, Spartan-6 constraints, non-GUI
   builds and programmer handoff.

## Buildroot and embedded Linux

No credible general-purpose Buildroot agent skill was found in the initial
search. NVIDIA Jetson and individual firmware projects contain Buildroot-related
skills, but they are board-specific and inappropriate as general instructions.

Authoritative sources:

- Buildroot: https://github.com/buildroot/buildroot
- Buildroot manual:
  https://buildroot.org/downloads/manual/manual.html
- Linux kernel: https://github.com/torvalds/linux

The repository's `AGENTS.md`, `docs/architecture.md` and
`docs/container-build.md` already form the beginning of our own appliance
skill. A later skill should cover reproducible container builds, BR2_EXTERNAL,
headless SuperCollider packaging, RAM-root generation, release manifests,
non-destructive GRUB candidate boots and A/B deployment safety.

## Norns

No complete norns Lua agent skill has been identified. Future searches should
start with:

- norns: https://github.com/monome/norns
- norns documentation: https://monome.org/docs/norns/
- maiden: https://github.com/monome/maiden

A local skill should cover script lifecycle, Lua APIs, clocks, params, grid,
MIDI, OSC schemas, deployment, log capture and safe restart.

## Next evaluation order

1. SuperCollider Pilot on Debian.
2. sc-designer-upgraded verification behaviour and license clarification.
3. Isolated RTL skill from digital-chip-design-agents.
4. Selected Daisy skills as references, followed by a project-specific skill.
5. Create local Pure Data/libpd, norns, iCE40 audio and Buildroot appliance
   skills around real container commands and tests.
