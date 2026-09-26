# Project context

Last updated: 2026-09-24

This is the canonical high-level handoff for humans and coding agents. Focused
contracts in the other documents remain authoritative for their own areas.
When facts conflict, prefer verified current hardware evidence and the most
recent focused decision record.

## Working principle

This project must save the operator's time. Coding agents should complete
bounded milestones autonomously, inspect the repository and machine before
acting, run every software-testable check, diagnose failures, preserve unrelated
work, commit and push cleanly, and request only unavoidable physical listening,
cabling, reboot, or musical decisions. Do not turn routine diagnosis into a long
series of commands for the operator to type.

## Purpose

Build a reliable, network-controlled SuperCollider performance realization
appliance from owned hardware. It is deliberately not a desktop DAW, an
autonomous mixing system, a conventional-console clone, or a replacement for
the sound design and effects in the connected instruments.

The appliance supports a three-person live setup, deterministic role-based song
programs, dry audio plus clock/event recording, virtual soundcheck, shared vocal
effects, later offline mix analysis, and eventually the Studer Dyaxis II
control surface. The intended final performance requires no routine live fader
riding after calibration, review and approval. See
`docs/performance-realization-engine.md` for the current product direction.

## Verified computer and audio hardware

Target computer:

- Dell OptiPlex 7010 Desktop;
- Intel Core i7-3770S, four physical cores/eight logical threads;
- 16 GiB RAM;
- 240 GB-class SSD;
- UEFI boot;
- conventional PCI slot;
- Debian 13 development/recovery installation.

Primary interface:

- original RME Project Hammerfall DIGI9652, PCI ID `10ee:3fc4`;
- Linux driver `snd_rme9652`;
- ALSA name `Digi9652`, device `hw:CARD=Digi9652,DEV=0`;
- JACK baseline: 48 kHz, 128 frames, two periods, realtime priority 70;
- ALSA/JACK exposes 26 capture and 26 playback channels;
- only the main bracket is installed: ADAT1 and ADAT2 provide 16 physical
  optical inputs and outputs;
- the ADAT3 expansion bracket is absent;
- channels 17-24 are software-visible but not physically present;
- channels 25-26 are S/PDIF;
- all 16 physically present ADAT output channels were previously confirmed.

Other available hardware:

- miniDSP MCHStreamer for portable development or another node;
- Audient iD44 for analogue I/O, microphones and monitoring;
- Studer Dyaxis II controller with motorized faders, encoders, buttons and
  heavy wheel;
- Dyaxis ADB keyboard/trackball already bridged through an Arduino Nano to USB
  serial;
- two rear RS-422 ports and network hardware remain future reverse-engineering
  work;
- two M5Stack AtomS3 Lite boards run the standalone
  `PlayableElectronics/usbmidi-over-espnow` bridge. Both boards were flashed
  from the same reliability-hardened image and verified by esptool on
  2026-09-24. The bridge presents native class-compliant USB-MIDI and uses
  automatic ESP-NOW pairing; its latest firmware commit is
  `3b6a32affa8ddc07450085ffecb9330ab4cc707b` and the flashed image SHA-256 is
  `3b1405204544390f93862dcffb49594fb974fa2782cb100a755b65a518d95604`.
- the verified Studer Dyaxis/MultiDesk U17 and Uptown Automation U7 firmware
  images are preserved and deliberately published at `dyaxis/firmware/`; their
  provenance and checksum manifest are in `dyaxis/firmware/README.md` and
  `SHA256SUMS`.

Current Dyaxis checksum status: the derived two-byte U17 application candidate
was physically programmed and read-back verified twice, but the console showed
`Checksum Failed` both times. No further candidate is authorized. The corrected
static path is marker mismatch -> checksum validation; `FDFE/FDFF` may remain
the stored checksum bytes during both reads. Before any logic-analyzer work,
use `dyaxis/analysis/U17_DS1230_CONTINUITY_TABLE.md` with power removed, then
follow the narrowly scoped passive capture in
`dyaxis/analysis/U17_LOGIC_ANALYZER_PROCEDURE.md`.

Never describe this installation as a 24-channel physical interface unless the
ADAT3 expansion hardware is added and verified. Keep the software data model
24-channel-capable, but validate active physical mappings strictly as 1-16.

## Operating-system architecture

### Debian workshop

Writable Debian is the development, build, hardware-test and recovery system.
It owns:

- Codex and Git;
- Docker Engine and Compose;
- direct access to the DIGI9652;
- SuperCollider development through pinned containers;
- Buildroot builds;
- payload compilation, testing and promotion;
- filesystem, GRUB and recovery operations.

Toolchains belong in purpose-specific containers rather than being installed
indiscriminately on Debian.

### Buildroot appliance

The performance system is a minimal native Buildroot Linux image booted by
GRUB, without Docker. Its verified baseline includes:

- Linux 6.12.107 with `CONFIG_PREEMPT_RT=y`;
- high-resolution timers and 1000 Hz kernel tick;
- built-in `snd_rme9652`;
- JACK2 and `scsynth`;
- networking and bounded boot diagnostics;
- physical recovery console and development SSH;
- immutable initramfs root unpacked into RAM;
- transient runtime/log state;
- validated compiled-payload loading.

The Buildroot root is ephemeral and effectively read-only. Reboot restores the
image state. Persistent musical payloads live outside the root image.

Debian remains the saved GRUB fallback. Candidate boots use a one-shot GRUB
entry so failed appliance boots return to Debian.

## Storage and payload ownership

The SSD currently contains:

- writable Debian root and EFI boot files;
- `/dev/sda3`, a 96 GiB ext4 filesystem labelled `SC_ADAT_DATA`;
- approximately 34 GiB trailing unallocated space.

The data partition is mounted:

- read-write at `/data` in Debian;
- read-only at `/data` in Buildroot.

Compiled releases use immutable versioned directories with
`current -> previous -> factory` validation and fallback. Debian compiles
authoritative `.scd` sources with pinned `sclang`, tests the resulting
SynthDefs against `scsynth`, and promotes only compiled payload artifacts.
Buildroot validates and consumes those artifacts; it never compiles source.

A separate disk is planned for multitrack recordings. Do not consume the
persistent payload partition as the long-term recording volume.

Normal SuperCollider code iteration must not require rebuilding Buildroot.
Rebuild the OS only when the kernel, drivers, JACK, SuperCollider runtime,
base services, or immutable factory payload changes.

## Proven native appliance baseline

The physical Buildroot candidate has booted successfully on the Dell with:

- PREEMPT_RT;
- Digi9652 detected;
- JACK at 48 kHz / 128 frames / two periods / RT priority 70;
- 26 capture and 26 playback JACK ports;
- `scsynth` ready;
- shared data partition mounted read-only;
- validated payload activation;
- zero startup xruns;
- usable network and recovery console.

QEMU tests cover structural boot and deterministic payload cases: valid current,
previous fallback, factory fallback and missing-data factory fallback. QEMU
cannot replace the physical RME/optical test.

## Current mixer milestone

Commit `90107bf` introduced the first Debian/Docker production mixer:

- 16 active one-to-one input/output paths;
- explicit production groups: kick, drums, bass, music_a, music_b, vocals, fx_a and fx_b;
- neutral unity scene;
- smoothed controls;
- bounded gains and protection;
- bypass;
- OSC set/query policy;
- bounded meters;
- 24-channel-capable data model with strict active-channel validation;
- dummy-JACK and physical DIGI9652 topology tests;
- `./lab mixer build|start|status|test|stop`.

The physical topology test proved 16 routes in each direction and left channels
17-26 disconnected. A 30-second silent test produced zero xruns/errors/clipping
and measured approximately 148 MiB RSS and 2.8% reported process CPU.

This does not yet prove real sample flow. The remaining physical milestone is
an end-to-end low-level signal test through all 16 inputs and outputs.

## Current clock and signal-flow investigation

Latest verified RME state:

- Sync Mode: Master;
- ADAT2 input: Lock Sync;
- ADAT1 input: No Lock;
- ADAT3 input: No Lock and physically unavailable.

ADAT2 Lock Sync proves that the RME is generating clock, the connected rack
receives it, and a synchronized optical stream returns on ADAT2. It proves
clock, not audible sample flow. ADAT1 currently has no valid return stream and
inputs 1-8 must not be treated as operational until that is resolved.

The immediate software priority is to stop relying on topology alone and add
bounded, self-cleaning diagnostics:

- `./lab mixer meters`: compact live peak/RMS for 16 inputs and 16 outputs,
  plus xruns;
- `./lab mixer tone --channel N`: safe default -30 dBFS, one output only,
  five-second automatic stop, channels 1-16 only;
- bounded input probe reporting which physical inputs contain samples;
- automated verification of actual non-zero samples, mixer buses and output
  mapping;
- inspection for zero/one-based channel or bus-offset errors.

Test output channel 9 first because it belongs to the clock-verified ADAT2 bank.

Clock management should become a canonical hardware-layer interface:

- `./lab audio clock status`;
- `./lab audio clock set master`;
- `./lab audio clock set autosync --source adat1|adat2`;
- `./lab audio clock set wordclock`.

Address the card by stable ALSA name, never assumed card number. Lock states are
read-only observations; commands set Sync Mode and Preferred Sync Source.
Status must distinguish No Lock, Lock and Lock Sync, include JACK rate, and
produce a concise health conclusion. The declared current default is internal
master at 48 kHz. Apply and verify it before JACK starts. Debian implementation
comes first; document the future Buildroot integration point without rebuilding
Buildroot during this diagnostic milestone.

## Mixer product scope

Initial live roles are approximately:

| Physical inputs | Working role |
| --- | --- |
| 1-8 | synthesizers, modular instruments and samplers |
| 9-16 | drum machine and percussion |

Vocals, vocal effects, spare returns and room/talkback require additional
physical I/O or revised allocation until ADAT3 exists.

Groups are first-class musical objects: kick, drums, bass, music_a, music_b,
vocals, fx_a and fx_b. Membership is explicit per song. Bass may originate from different
hardware in different songs; the system never classifies or rearranges it.

Live processing is intentionally restrained:

- trim, polarity, HPF, mute, solo and level;
- practical corrective EQ;
- dynamics only where deliberately configured;
- broad group EQ/level/gentle compression;
- a small number of shared vocal delay/reverb sends;
- monitor buses;
- dry recording, markers, scenes and virtual soundcheck.

The appliance must never perform automatic EQ, source recognition, gain riding,
adaptive compression, automatic routing, live spectral correction, autotuning,
or unapproved analysis-driven changes.

Offline Debian analysis may later identify masking, mud, rumble, harshness,
peaks, level inconsistency and intelligibility problems. It produces evidence,
bounded proposals and loudness-matched A/B renders. Human approval is required
before any setting becomes a live scene. Prefer group-level corrections first,
then individual channels, and only then subtle frequency-selective sidechain
processing when justified. Avoid audible ducking and pumping.

## Control and automation architecture

The agreed decision is recorded in
`docs/sc-adat-control-architecture-decision.md`.

Responsibilities:

- `scsynth`: realtime audio graph, sample-accurate application, smoothing and
  metering;
- headless `sclang`: authoritative mixer state, OSC API, validation, scenes,
  song markers, transport, automation, MIDI and scheduled bundles;
- Open Stage Control: replaceable browser control surface only;
- future Dyaxis: physical surface using the same logical control contract.

Do not build a separate generic OSC sequencer. Use SuperCollider's native
`TempoClock`, `SystemClock`, `Routine`, `Task`, Patterns, `OSCdef`,
`MIDIdef` and timestamped OSC bundles. Use DSP-side ramps instead of streams
of intermediate control messages.

A scene is a deterministic baseline. A timeline is an explicit validated set
of events and ramps. Automation must be visibly armed. Manual movement suspends
automation for that parameter until the next marker or explicit re-enable.
Stopping automation never stops audio. Invalid automation leaves the current
static mix untouched. No adaptive live decisions are allowed.

Develop the control engine in the existing Debian SuperCollider container.
Once stable, evaluate adding headless `sclang` to Buildroot without the IDE or
Qt GUI components.

## First virtual control surface

Use Open Stage Control in a separate pinned, unprivileged, headless container:

- no `/dev/snd`;
- no JACK;
- no realtime capabilities;
- no authoritative state;
- layout stored in Git;
- read-only layout mount;
- browser clients on Mac/tablet/phone;
- runs on Dell Debian during development;
- runs on an external Docker host, initially the Mac, while Dell boots
  Buildroot.

Initial pages:

1. overview: groups, master, scene and health;
2. channels 1-8;
3. channels 9-16;
4. groups;
5. system/clock/payload/xruns.

Meter traffic should be bounded and droppable, initially approximately 10-20
Hz. Commands and state confirmations are immediate. The OSC namespace must be
surface-independent so Open Stage Control, norns and Dyaxis can coexist.

## CPU strategy

The current `scsynth` DSP graph is effectively single-threaded, although
JACK, `sclang`, networking and system work use other cores. Keep
`scsynth` as the stable baseline and collect average/peak DSP load, per-thread
CPU and xruns under the real maximum mixer workload.

SuperCollider's `supernova` is the measured multicore upgrade path. If actual
peak DSP load leaves insufficient headroom, compare a deliberately staged
`ParGroup` graph: independent channel strips in parallel, independent group
processors in parallel, then ordered master/output stages. Do not switch merely
because the CPU has multiple cores.

## Development order from here

1. Prove actual sample flow, terminal meters and safe per-output tone.
2. Add deterministic RME clock status/set commands and boot-time verification.
3. Complete the real 16-input/16-output physical test.
4. Replace the temporary Python-authoritative mixer policy with the agreed
   headless `sclang` authoritative control model without regressing DSP.
5. Add the separate Open Stage Control container and bidirectional surface.
6. Stabilize scenes, markers and native SuperCollider automation.
7. Add dry multitrack recording to the separate recording disk.
8. Add monitor buses and shared vocal sends.
9. Add virtual soundcheck.
10. Add offline advisory analysis and A/B review.
11. Integrate norns and later reverse-engineer/map Dyaxis.
12. Evaluate supernova only from measured need.

Do not rebuild or stage Buildroot while completing Debian-only control,
metering and clock diagnostics unless a proven immutable-runtime dependency
requires it and the deployment gate is explicitly approved.

## Safety and release invariants

- Preserve Debian as the recoverable saved boot target.
- Building artifacts never grants permission to stage, alter GRUB or reboot.
- Stage only validated byte-identical artifacts.
- Never overwrite the running or last-known-good appliance state.
- Keep the live audio path deterministic when control, analysis or recording
  components fail.
- Invalid payloads/scenes/configuration must fall back safely.
- Generate no loud or multi-output test signal by default.
- Physical tests require bounded duration and automatic cleanup.
- Keep machine identifiers, private keys and generated local diagnostics out of
  Git.
