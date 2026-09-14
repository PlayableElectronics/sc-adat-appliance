# Project context

## Intent

Build a low-cost, reliable, network-controlled SuperCollider instrument around
hardware already owned. The target is not a general desktop workstation. It is
a headless synthesis appliance with deterministic boot, low scheduling jitter,
multichannel ADAT, remote development, and a recoverable update path.

The project also serves as an embedded-Linux learning platform: Debian is the
workshop, while Buildroot produces the sealed instrument.

## Target computer

A used Dell OptiPlex 7010 is on its way.

Expected configuration:

- Intel Core i7-3770S, four cores and eight threads, up to 3.9 GHz
- 16 GB DDR3
- SSD
- original conventional PCI slot
- NVIDIA GeForce GT 730 currently installed

Planned physical changes:

- remove the GT 730;
- use Intel integrated graphics only for installation and diagnostics;
- remove the separate HDD and use the SSD alone;
- install the RME DIGI9652 in its native PCI slot.

Nothing about the received machine is considered verified until Debian records
the actual CPU, RAM, firmware mode, storage, PCI topology, thermals, network
interface, and RME detection.

## Audio hardware already available

### RME DIGI9652

This is the original Project Hammerfall DIGI9652, not the later HDSP 9652.

- conventional PCI
- three ADAT optical inputs
- three ADAT optical outputs
- up to 24 channels each direction at 44.1/48 kHz
- Linux driver: `snd-rme9652`
- do not use `snd-hdsp`, `hdspconf`, or HDSP-specific assumptions without
  independently proving they apply

This is intended to be the permanent interface for the appliance.

### miniDSP MCHStreamer

Available as a class-compliant USB multichannel/ADAT interface. Keep it free for
portable development, newer computers without legacy PCI, comparison testing,
or a second synthesis node. It is not required by the primary appliance.

### Audient iD44

Available for analogue recording, microphones, instruments, monitoring, and
studio routing. It should not be consumed merely as the primary appliance's
ADAT adapter when the DIGI9652 is available.

### ADAT development hardware

Available AL1402G decoder and AL1401AG encoder chips support a longer-term FPGA
ADAT routing/matrix project. The current appliance must remain useful without
waiting for that router.

## Control architecture

A monome norns Shield on Raspberry Pi is intended as a tactile controller,
sequencer, display, MIDI/grid integration point, and musical clock source.

The initial boundary is explicit:

- norns Lua handles keys, encoders, screen, grid, clocks, patterns, and user
  interaction;
- the Dell handles synthesis and audio;
- control travels over wired Ethernet as OSC;
- ADAT carries audio from the Dell;
- do not initially replace or deeply modify norns' local
  matron/crone/sclang/scsynth relationship;
- implement the remote synth as a purpose-built OSC service.

Wi-Fi may be used for development, but wired Ethernet is preferred for
performance control.

## SuperCollider model

Build both `scsynth` and `supernova` initially.

Ordinary `scsynth` does not automatically distribute one large synthesis graph
over all CPU cores. Compare:

- a single `scsynth`;
- multiple independent server processes where useful;
- `supernova` with deliberately separated parallel groups.

Relevant intended workloads include modal and inharmonic banks, FM synthesis,
physical modelling, resonators, granular processing, reverbs, analysis, and
multichannel routing. Start with measured, deterministic workloads before
porting experimental instruments.

Initial validation target:

- 48 kHz;
- 128-sample buffer;
- 24-channel routing;
- no xruns during the defined interference test;
- test 64 samples only after the baseline is stable.

## Operating systems

### Debian

Normal writable installation used for:

- Codex;
- Git and repository work;
- native SuperCollider development;
- Buildroot builds;
- hardware inspection;
- latency and DSP benchmarking;
- GRUB management;
- appliance deployment and recovery.

Debian does not need to be read-only.

### Buildroot appliance

Minimal read-only performance system containing only the validated components
needed for networking, remote administration, the RME card, SuperCollider, and
supervision.

Do not include a graphical desktop, Qt IDE, PipeWire, PulseAudio, Bluetooth, or
Wi-Fi unless a later measured requirement justifies one.

Use tmpfs for transient writes. Persistent configuration, SynthDefs, and
approved recordings belong on a separate data filesystem.

## Boot and storage plan

The SSD is expected to contain:

- EFI/GRUB or a legacy-BIOS equivalent, determined after inspection;
- writable Debian;
- separate shared data;
- immutable Buildroot slot A;
- immutable Buildroot slot B.

A/B invariants:

- write only the inactive slot;
- never overwrite the running slot;
- never overwrite the last-known-good slot;
- Debian remains selectable for rescue;
- Debian remains the default until an appliance candidate passes validation;
- use filesystem UUIDs in persistent boot configuration;
- do not finalize sizes or commands before inspecting the real SSD and firmware
  mode.

## Real-time policy

Linux 6.12 or newer contains the mainline PREEMPT_RT infrastructure for x86, but
the selected kernel must explicitly enable `CONFIG_PREEMPT_RT=y`.

PREEMPT_RT is intended to reduce worst-case scheduling latency and xruns. It
does not increase raw DSP throughput.

Begin with conservative configuration. Defer CPU isolation, tick isolation,
forced IRQ affinity, disabled C-states, unlimited RT runtime, and similar
tuning until baseline measurements demonstrate a need. Make one change at a
time and retain comparable results.

## SuperCollider integration research

Two useful upstream/community components were identified:

- `sc-designer`: a lightweight agent skill for SuperCollider sound design;
- `supercollider-pilot`: agent skills plus an MCP server capable of managing a
  persistent sclang session, executing files, rendering audio, capturing logs,
  and recovery.

There was no comparably complete ready-made norns Lua skill. A project-specific
norns development skill may later cover the norns API, OSC protocol, script
layout, deployment, logs, and safe restart workflow.

Do not add either component blindly to the appliance. Evaluate it first under
Debian and keep the performance image minimal.

## First session on the Dell

1. Inspect the physical machine and remove the GT 730.
2. Install the DIGI9652.
3. Install a normal writable Debian system without repartitioning for the final
   A/B design prematurely.
4. Clone this repository and let Codex read `AGENTS.md`.
5. Run `scripts/collect-hardware-baseline`.
6. Review the report for sensitive identifiers before committing selected
   facts.
7. Confirm `snd-rme9652`, ALSA devices, clock state, and every ADAT bank.
8. Establish Debian audio and latency baselines at 48 kHz/128 samples.
9. Test native headless SuperCollider.
10. Only then pin Buildroot, Linux, and SuperCollider versions and complete the
    Buildroot package.

## Current unknowns

- actual SSD model, capacity, health, and current partition table;
- UEFI versus legacy BIOS installation;
- precise motherboard and BIOS revision;
- exact PCI IRQ routing with the DIGI9652 installed;
- actual RME card revision and clock behaviour;
- stable ALSA device naming and channel ordering;
- stable buffer size under representative DSP and network load;
- whether `scsynth`, `supernova`, or multiple servers best fit the intended
  instruments;
- final Buildroot and kernel release;
- final SuperCollider dependency set and headless build flags;
- final A/B partition sizes and GRUB workflow.

Resolve these with evidence from the target rather than assumptions.
