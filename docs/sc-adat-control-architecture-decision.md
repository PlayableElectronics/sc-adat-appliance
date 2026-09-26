# SC-ADAT control and automation architecture decision

Date: 2026-09-16

Status: agreed

## Decision

Do not build a separate general-purpose OSC sequencer. Use SuperCollider's existing language-side sequencing facilities.

- `scsynth` remains the realtime DSP engine.
- Headless `sclang` becomes the authoritative mixer-control and automation engine.
- Open Stage Control is a replaceable virtual surface only.
- The future Studer Dyaxis controller uses the same logical OSC contract.
- MIDI, transport and external clock input terminate in `sclang`, not in a new custom sequencing service.

## Responsibilities

### scsynth

- Audio routing and processing.
- Sample-accurate parameter application.
- Click-free ramps using DSP-side `Lag`, `Line`, `Env` or equivalent mechanisms.
- Meter generation at a bounded rate.

### sclang

- Authoritative mixer state.
- OSC API and validation.
- Scene loading and saving.
- Song markers and transport.
- Time-based and beat-based automation.
- Manual override policy.
- Automation gesture recording and later simplification into ramps.
- Scheduled OSC bundles sent ahead to `scsynth`.
- MIDI input, clock and transport integration when required.

Use native facilities such as `TempoClock`, `SystemClock`, `Routine`, `Task`, Patterns, `OSCdef`, `MIDIdef` and timestamped OSC bundles. `Score` is reserved for non-realtime/offline work.

### Open Stage Control

- Runs in its own pinned, unprivileged, headless container.
- Has no audio device, JACK, realtime capabilities or authoritative state.
- Provides browser-based controls, meters and feedback.
- Runs on Dell Debian during development and on an external Docker host, initially the Mac, while the Dell is booted into Buildroot.

## Scenes and automation

- A scene establishes an explicit deterministic baseline.
- A song timeline contains explicit validated events and ramps.
- No adaptive, audio-reactive or inferred mix decisions are allowed.
- Automation is visibly armed or disarmed.
- Manual control suspends automation for that parameter until the next marker or explicit re-enable.
- Stopping automation never stops audio.
- Missing or invalid automation leaves the mixer in its current static state.
- Routing changes and dangerous gain changes require explicit permission.
- All executed automation events are logged.

The initial rehearsal/performance clock source is the modular system, supplying
both accurate MIDI Clock/transport and an analogue pulse with run/reset where
available. `sclang` follows and timestamps the clock against the audio sample
timeline; it does not repair the live clock or silently become master. Clock
loss is logged and reported while audio recording continues. A manually
started monotonic clock remains available for development without external
hardware. MTC, Link, LTC and an explicitly selected appliance-master mode may
be added later behind the same transport abstraction.

Raw received timing and any derived tempo map are distinct artifacts. Exact
replay may use captured sample positions; a reviewed reconstruction may use a
derived stable tempo map. Derived timing never overwrites the raw capture.

## Deployment path

1. Develop and test `sclang` control code in the existing Debian SuperCollider container.
2. Develop the Open Stage Control surface in its own container.
3. Keep the OSC contract independent from both surfaces.
4. Once stable, investigate adding headless `sclang` to Buildroot without the IDE, Qt GUI or development components.
5. Do not add a custom sequencing daemon unless a concrete requirement cannot be expressed reliably using native SuperCollider facilities.

## Consequence

The appliance uses SuperCollider as both its DSP platform and its native scheduling language. Project code describes mixer-specific state, safety rules, scenes and timelines; it does not reimplement clocks, pattern playback, MIDI handling or OSC scheduling.
