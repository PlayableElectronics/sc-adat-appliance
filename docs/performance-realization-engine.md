# Performance realization engine

Date: 2026-09-26

Status: agreed product direction

## Relationship to the Production Runtime Boundary

The production appliance follows the normative boundary in
[architecture.md](architecture.md#production-runtime-boundary--architectural-decision).
SuperCollider MUST remain the sole live authority. Normal stereo performance
MUST run headlessly without Python, Chataigne, a Mac, a web interface, an
automation engine, or a network. Chataigne is an optional rehearsal and
creative-authoring client; it MUST NOT become a boot, audio, safety, or
normal-stereo dependency. Python analysis is offline/development and advisory
only, never an automatic live controller.

## Decision

The appliance is not intended to become a software clone of a conventional
analogue or digital console. Its long-term purpose is to turn decisions made
during rehearsal into deterministic, versioned song programs that require no
routine mixing during the final performance.

The current stereo and quad group mixers remain the low-level renderer and
diagnostic foundation. Future work should build a role-based performance and
recording system above that foundation instead of adding a conventional channel
strip, fader and routing feature merely because it exists on ordinary consoles.

## Performance contract

After source mapping, calibration, recording, offline review and musical
approval, the appliance should run headlessly without requiring the performer
to ride group or channel faders.

During a final performance it must:

- reproduce the approved song program deterministically;
- preserve expression already produced by synthesizers, modular envelopes,
  samplers, drum machines, vocals and external effects;
- execute only explicitly authored cues, ramps and spatial movements;
- keep recording even if musical clock is lost;
- report clock, recording, xrun, overload and scene health clearly;
- provide emergency attenuation, mute and a known-safe fallback;
- never infer, rewrite or automatically correct the mix.

No live source recognition, automatic gain riding, adaptive EQ, automatic
scene writing, live spectral correction or silent clock failover is allowed.

## Four layers

### 1. Source and calibration layer

This layer represents physical reality and should remain stable across songs:

- physical input identity;
- fixed calibration trim and polarity;
- optional corrective high-pass filtering;
- nominal level and headroom target;
- signal, overload and clock health;
- dry pre-creative-processing recording.

Every source still has a digital gain coefficient, but ordinary performance
faders are not the primary interface. Calibration trims are set deliberately
and then locked. Connected instruments retain responsibility for their own
performance envelopes and local level controls.

### 2. Musical-role layer

Processing is owned primarily by musical function, not permanently by a
physical channel. The initial eight roles are:

1. kick or foundation;
2. drums and rhythm;
3. bass;
4. music A or foreground;
5. music B or background;
6. vocals;
7. effects A or transformation/foreground effects;
8. effects B or space/atmosphere.

Source-to-role membership is explicit and stored per song. A sampler may be
bass in one song and a foreground texture in another. The engine never guesses
or changes that membership.

Role treatments should express musical intent such as weight, presence,
brightness, density, depth, transient/body balance, saturation, width and
stereo/quad position. Conventional gain, EQ and dynamics may implement those
decisions internally, but an eight-fader console is not the product model.

Effects returns are first-class musical roles rather than secondary utility
returns. They may carry transformed foreground material, feedback textures or
spatial atmosphere and receive their own authored treatment and movement.

Low-pass-gate-like or other timbral amplitude treatments are valid when chosen
for a specific role or song. They must be explicit, bounded and rehearsed.
Unapproved envelope-following or adaptive behaviour is not permitted.

### 3. Song-program layer

A song program is a human-readable, versioned and validated description of:

- source-to-role mapping;
- approved role balance;
- tone, dynamics and effect relationships;
- stereo or quad rendering;
- explicit sends and sidechains;
- authored spatial movement and other automation;
- section markers and transitions;
- the exact calibration, analysis and software versions used for approval.

Continuous parameters use bounded ramps. Routing and mute changes occur only
at explicit cues. Hardware calibration is not changed by song recall.

Song transitions may be triggered manually, by MIDI/OSC transport, by
Chataigne, or by an authored timeline. There is no automatic response to audio
content. If a program is invalid, the current known-good program remains active.

### 4. Safety and observation layer

The live surface should prioritize:

- current and next song;
- loaded-program identity and validation state;
- audio and MIDI-clock health;
- recording status and available storage;
- overloads, xruns and missing inputs;
- start/stop or previous/next cue;
- emergency attenuation and mute;
- safe neutral fallback.

Detailed faders, thresholds and filters remain available during authoring and
diagnosis, but are not the normal performance view.

## Authoring and review workflow

The intended workflow is:

1. map and calibrate sources;
2. record a rehearsal with raw audio, clock and events;
3. run offline spectral and statistical analysis;
4. review evidence and proposed changes;
5. audition loudness-matched alternatives through virtual soundcheck;
6. approve, edit or reject every change;
7. compile an immutable song program;
8. rehearse that exact program;
9. activate it for the performance.

Offline analysis is an adviser, never a live controller. It may identify mud,
masking, rumble, harshness, inconsistent role balance, phase problems or vocal
intelligibility issues. It may propose static group treatment and, only when
justified, shallow frequency-selective sidechain processing. Nothing becomes
active until it is listened to and approved. Python-generated recommendations
MUST remain advisory artifacts until a human explicitly accepts them into a
reviewed SuperCollider program.

Chataigne and the future Dyaxis integration are principally authoring,
rehearsal and explicit-cue tools. Chataigne MAY support attended quad
movement, but losing it MUST leave SuperCollider on its last valid value. The
final performance should not depend on a touchscreen or an operator
continuously manipulating a virtual mixer.

## Recording and clock contract

### Clock authority

The initial performance clock master is the modular system. It can provide both:

- an accurate MIDI Clock stream with transport messages; and
- an analogue clock pulse, plus run/reset signals when available.

The appliance is a clock follower, recorder and timestamp authority. It must
not silently regenerate, smooth, repair or take ownership of the live clock.
Clock ownership is explicit and fixed for a session. A later appliance-master
mode is allowed only as a separately selected and rehearsed configuration.

If clock is lost, the appliance continues recording audio, records a
`clock-lost` event, reports the fault and does not automatically become master.

### Captured events

At minimum, capture and preserve:

- MIDI Clock (`0xF8`);
- Start (`0xFA`), Continue (`0xFB`) and Stop (`0xFC`);
- Song Position Pointer (`0xF2`) when supplied;
- analogue clock, run and reset edges when connected;
- song and section markers;
- scene and cue changes;
- authored and manual OSC/MIDI control events;
- clock loss, restart, missing-pulse and transport-discontinuity events.

Every event is timestamped against the authoritative audio sample timeline.
The event record must preserve the correspondence between each received clock
or control event and an absolute audio sample position. MIDI Clock alone is
relative tempo information; the sample timeline and markers provide the
session location.

The appliance may calculate BPM, jitter, missing pulses and clock health for
review, but these observations do not alter live timing.

### Session bundle

Audio and control data belong to one recoverable session bundle rather than
being forced into one file:

```text
session-YYYYMMDD-HHMMSS/
  audio/
    input-01.wav ... input-16.wav
    role-*.wav                 optional
    master-stereo.wav          optional
    master-quad-*.wav          optional
    clock-pulse.wav            optional raw verification track
  midi/
    raw-clock.mid
    derived-tempo-map.mid
  events/
    timeline.jsonl
    markers.json
    automation.jsonl
  session.json
  SHA256SUMS
```

The precise container and file layout may evolve, but the contract is:

- dry audio is never replaced by processed audio;
- raw clock/event capture is never overwritten by a derived tempo map;
- every stream can be aligned through absolute sample positions;
- long audio files use a recoverable large-file format such as RF64;
- the bundle records source/role mapping, song-program versions, sample rate,
  clock source, clock statistics, xruns, software versions and checksums.

Where practical, record the analogue pulse as a raw verification track in
addition to MIDI Clock. A dedicated digital MIDI connection remains the primary
clock input; audio transient detection is not the sole clock source.

### Reproduction

Recorded timing supports two explicit later modes:

1. **Exact performance replay** schedules events at their captured audio-sample
   positions and preserves intentional tempo variation.
2. **Derived reconstruction** uses a reviewed tempo map to generate a stable
   clock for editing or virtual soundcheck.

The derived version is a new artifact and never replaces the raw capture.

## Development priorities

After the current stereo/quad renderer is proven physically, prioritize:

1. recoverable multitrack recording on the planned recording disk;
2. sample-timestamped MIDI Clock/transport and analogue pulse capture;
3. session bundles, markers and versioned metadata;
4. source calibration and explicit source-to-role mapping;
5. virtual soundcheck using the exact live graph;
6. offline advisory reports and A/B renders;
7. immutable song programs and explicit transitions;
8. minimal performance health and emergency controls;
9. role-oriented timbral and spatial treatments justified by recordings.

Do not prioritize a general-purpose console UI, banks of channel strips, live
fader riding, automatic mixing, or feature parity with products such as an
MR18. New work must demonstrate how it improves calibration, authoring,
recording, deterministic reproduction, safety or musical role realization.
