# Instrument and mixer ideas

This document preserves experimental directions for the appliance. These are
design possibilities, not requirements for the first implementation.

The first milestone remains a safe, measurable 24-channel grouped mixer.
Experimental features must be added incrementally without destabilizing that
baseline.

## Foundation: programmable 24-channel mixer

At 44.1/48 kHz, the RME DIGI9652 provides three banks of eight ADAT inputs and
outputs. SuperCollider can provide:

- 24 input strips;
- flexible input-to-output routing;
- subgroups;
- pre- and post-fader sends;
- shared effects;
- independent monitor and cue mixes;
- direct outputs;
- smooth scene recall;
- meters, mute, solo, PFL, and output protection;
- OSC control from norns and other devices.

A provisional output assignment might reserve stereo mains, multiple monitor
mixes, direct outputs, external effects, and experimental FPGA routes. No fixed
mapping should be adopted until hardware channel order is verified.

The graph order should remain explicit:

```text
hardware inputs
-> input processing
-> subgroups and sends
-> effects returns
-> monitor mixes
-> output protection
-> physical outputs
```

Persistent input, bus, effect, and output synths are preferred over repeatedly
rebuilding one enormous matrix SynthDef. Routing gains should change smoothly.

## 1. The laboratory as one instrument

Treat every connected device as a node in a distributed instrument:

- SuperCollider voices and processors;
- norns and softcut;
- Daisy processors;
- FPGA oscillators and routing;
- microphones and pickups through converters;
- analogue or digital external effects;
- future RP2040/ESP32 audio nodes.

A scene recalls an instrument topology rather than merely a set of mixer
levels. One gesture may morph routing, feedback, resonators, spatial position,
and the balance between physical and synthetic sources.

## 2. Controlled optical feedback matrix

Route signals from SuperCollider through ADAT to external digital, FPGA, or
analogue processing and return them through ADAT inputs.

Possible uses:

- Karplus-Strong structures spanning devices;
- evolving cross-feedback between many channels;
- physical objects inserted into digital resonators;
- feedback networks with per-path filtering, delay, saturation, and decay;
- freezing the state of the whole laboratory.

Every feedback path requires bounded gain, smoothing, DC protection, invalid
signal protection, and an emergency mute. A future FPGA router may provide a
hardware safety layer that remains active if Linux fails.

## 3. Spectral traffic controller

Analyze incoming channels and route them according to musical features rather
than fixed channel assignments.

Candidate features:

- amplitude and envelope;
- transient/onset activity;
- estimated pitch and pitch confidence;
- spectral centroid or brightness;
- noise versus tonal character;
- energy in a small filter bank;
- temporal stability.

Example behaviours:

- bass-rich material enters one processor;
- transients excite metallic resonators;
- stable pitches feed modal or additive resynthesis;
- noisy components enter granular processing;
- quiet channels borrow spectral energy from active channels;
- routing density changes with aggregate spectral activity.

The first version should use inexpensive analysis such as envelopes, onset
detection, pitch confidence, and a small filter bank. FFT routing is a later
option, not a prerequisite.

## 4. Twenty-four-node scanned instrument

Treat channels and internal buses as masses or nodes in a physical network.
Routing connections behave as springs or couplings. Inputs apply force and
outputs observe different points in the network.

Nodes may exist in different devices:

- SuperCollider;
- FPGA;
- Daisy;
- norns/softcut;
- analogue feedback paths.

This extends the existing scanned-synthesis interest from one simulated string
into a distributed electro-optical resonating structure.

## 5. Hardware resynthesis farm

Analyze a captured sound and distribute reconstruction tasks:

- low modes to an FPGA modal/sine bank;
- noisy attack to Daisy;
- sustained spectral body to SuperCollider;
- transient fragments to softcut;
- ambience to shared multichannel effects.

Return each component as an independent ADAT stem. Run software reference and
hardware candidate implementations simultaneously for listening, spectral
comparison, and null testing. Stable SuperCollider components can gradually be
ported to Faust, Daisy, or FPGA.

## 6. Spatial routing as timbre

Outputs do not need to correspond only to speakers. A spatial coordinate can
select both audible destination and processing path.

Example allocation:

- speakers;
- external effect inputs;
- feedback returns;
- recording stems;
- diagnostic and preview routes.

Moving a source changes where it is heard and what hardware it encounters.
Norns can display and manipulate the map.

## 7. Time-travelling mixer

Maintain a rolling circular buffer for every input or selected internal bus.
Every route may select both a source and a time offset.

Possible sources for one destination include:

- live input;
- the same input 100 ms ago;
- the previous beat;
- a fragment several seconds old;
- a frozen historical window.

Connections therefore have at least source, destination, gain, delay, feature
condition, attack, release, and feedback limit.

A valuable interaction is retrospective capture: recording is always occurring
in a rolling history, so a performer can capture an interesting moment after it
has happened.

## 8. Multichannel sound-on-sound looping

The circular-buffer infrastructure also supports sound-on-sound recording:

```text
new_buffer = previous_level * old_buffer + record_level * input
```

Loop points may exist at:

- physical inputs;
- processed input strips;
- subgroups;
- effect returns;
- monitor mixes;
- feedback paths;
- complete multichannel matrix states.

Loop modes:

- fixed tape loop;
- persistent overdub;
- gradually decaying overdub;
- frozen playback;
- routed loop whose destination changes each pass;
- spectral loop that replaces selected bands;
- event loop that records control and analysis;
- variable-rate or reverse loop;
- external loop that travels through ADAT hardware;
- fragment cloud drawn from several historical loops.

Each revolution may follow a different path:

```text
clean -> modal resonator -> filtered delay -> spectral route -> external node
```

At 48 kHz and 32-bit samples, 24 channels require approximately 4.6 MB/s,
276 MB/minute, or 2.76 GB for ten minutes. Prefer short history on all channels
and long loops on selected channels or subgroups. Use SSD recording for
archival takes rather than as the primary real-time loop store.

## 9. Spectral time-routing matrix

Combine ideas 3, 7, and 8. Each route selects:

- an input or internal bus;
- a historical offset or loop layer;
- a destination;
- gain;
- spectral or temporal activation conditions;
- fade behaviour;
- a feedback safety limit.

A note can send its current transient to a resonator, an earlier low-frequency
body into feedback, stable pitch to a modal bank, and its quiet tail into a
memory cloud. The source continuously rewires the system according to its
spectral structure and history.

## 10. Autonomous patch ecosystem

Define behaviours rather than static routing:

- connections grow and decay;
- active paths inhibit neighbouring paths;
- unused nodes accumulate potential;
- transients create connections;
- stable feedback networks can be captured as scenes;
- unstable networks are automatically attenuated;
- mutation changes topology while preserving hard safety limits.

Norns controls density, persistence, mutation, stability, and history depth
instead of exposing every matrix coefficient.

## 11. FPGA as optical nervous system

A future FPGA ADAT router may divide responsibility as follows:

- FPGA: sample-accurate base routing, clock-domain handling, emergency mute,
  hard gain limits, and fallback silence or pass-through;
- SuperCollider: analysis, synthesis, effects, time memory, and evolving rules;
- norns: tactile performance control and visualization;
- microcontrollers: satellite voices, effects, and sensors.

The base mixer must not depend on this future FPGA layer, but interfaces should
allow it to be introduced later.

## 12. Compile the patch into hardware

Use SuperCollider as the reference implementation and measurement environment.
Profile the graph, identify stable components, and port selected modules to
Faust, Daisy, RP2040, or FPGA. Compare reference and candidate concurrently over
separate ADAT channels.

## Norns performance concept

Norns should expose musical behaviours, not a raw 24 by 24 matrix.

Possible pages:

- TIME: history depth, delay spread, rhythmic quantization;
- SPECTRUM: band focus, pitch/noise balance, feature sensitivity;
- ROUTING: density, persistence, topology, and mutation;
- FEEDBACK: amount, damping, stability margin, and emergency state;
- LOOP: source, length, overdub retention, record level, and transformation;
- SCENE: save, recall, crossfade, freeze, and randomize.

Possible primary gestures:

- E1: history depth or selected object;
- E2: spectral selectivity or retained previous layer;
- E3: routing instability or transformation amount;
- K2: retrospective capture or loop boundary;
- K3: overdub/freeze/mutate depending on page;
- deliberate key chord: emergency mute or destructive clear.

The final mapping must remain consistent and provide clear visual feedback.

## Implementation sequence

1. Muted 24-channel hardware enumeration and channel identification.
2. Stable grouped mixer with output protection.
3. Input strips, subgroups, effects sends, and monitor buses.
4. Scene serialization and smooth recall.
5. Short rolling buffers and manually controlled delayed routes.
6. Sound-on-sound loops on selected buses.
7. Lightweight analysis and feature-driven routing.
8. Combined spectral time-routing.
9. External ADAT feedback with strict safety controls.
10. Distributed FPGA/Daisy/norns nodes.
11. Autonomous topology and hardware migration experiments.

At each stage preserve a known-good conventional mixer mode that can be selected
without experimental routing, feedback, or autonomous behaviour.
