# Milestone: deterministic live console and offline mix review

> Product-direction update (2026-09-26): the long-term appliance is a
> role-based performance realization engine, not a conventional console clone.
> The current mixer is its low-level renderer. The accepted performance,
> authoring, recording and clock contract is documented in
> [performance-realization-engine.md](performance-realization-engine.md) and
> takes precedence where this earlier milestone assumes routine live fader or
> channel-strip operation.

## Purpose

Turn the SC-ADAT appliance into a dependable live console, multitrack recorder,
and virtual-soundcheck system for a three-person performance. It is not a DAW,
an instrument-effects replacement, or an autonomous mixing system.

The appliance must save operator time while keeping every audible decision
explicit, stable, reviewable, and reversible.

## Performance input plan

The exact allocation remains configurable per show, but the initial working
layout is:

| ADAT inputs | Default role |
| --- | --- |
| 1-8 | synthesizers, modular instruments, and samplers |
| 9-16 | drum machine and percussion |
| 17-20 | vocals and vocal-effects returns |
| 21-24 | spare inputs, room microphones, talkback, or external returns |

Musical roles are metadata, not automatic routing rules. Bass may come from a
sampler in one song and a modular synthesizer in another. The engine must not
guess source roles or alter processing in response.

## Live scope

The items below describe low-level DSP capability, authoring access and
diagnostics. They do not imply that conventional channel strips or volume
faders belong on the final performance surface. Calibration trims are set and
locked; approved role balance is stored in song programs; normal performance
should require no live gain riding.

The initial live engine should provide:

- 24 fixed, explicit input paths and ADAT outputs;
- input trim, polarity, high-pass filter, practical parametric EQ, mute, solo,
  and level;
- lightweight gate or compression only on channels where it is deliberately
  configured;
- instrument, drum, and vocal groups;
- independent monitor buses for the three performers;
- a small number of shared send effects, initially one vocal reverb and one
  vocal delay;
- dry 24-channel recording, with optional group stems and stereo master;
- song and section markers;
- versioned scene capture and recall;
- virtual soundcheck using recorded dry tracks;
- bounded metering, xrun reporting, and a known safe bypass/baseline state.

Synthesizers and drum machines retain their own sound design and effects. The
appliance integrates, balances, records, monitors, and recalls them.

## Deterministic behaviour contract

Nothing changes during a performance unless it was explicitly saved in the
selected scene or deliberately changed by a performer or operator.

The live engine must never perform:

- automatic EQ or spectral correction;
- source or instrument recognition;
- automatic gain riding;
- adaptive compression;
- automatic routing;
- automatic scene writing;
- live autotuning or pitch correction;
- unapproved analysis-driven changes.

A scene change uses bounded ramps for continuous parameters. Routing and mutes
change only on explicit cues. Effect tails should survive scene changes where
possible. Monitor mixes and hardware calibration are excluded from song recall
unless explicitly opted in.

Manual changes are logged as events but are not silently written into the
stored scene.

## State hierarchy

1. **Show baseline** — hardware routing, channel calibration, safety limits,
   monitor topology, and emergency bypass. This is locked during performance.
2. **Song scene** — explicit levels, mutes, EQ, dynamics, sends, and group
   assignments for one song.
3. **Section cue** — a small intentional delta such as a mute, level change, or
   vocal delay throw.
4. **Manual performance state** — operator and performer changes, logged without
   modifying the approved scene.

Every stored state is human-readable, versioned, validated before activation,
and has an explicit rollback path.

## Recording and markers

Record all 24 inputs dry so later processing decisions never destroy the source.
Optionally record the instrument, drum, and vocal groups plus the stereo master.

The recording must also capture MIDI Clock and transport, the available
analogue clock/run/reset signals, and all markers and control events against the
same absolute audio-sample timeline. The modular system is the initial clock
master. The appliance follows and records it without automatic correction or
silent failover. See the dedicated performance-realization decision for the
complete clock-loss and session-bundle contract.

Markers must include at least:

- session and take identity;
- song and section;
- absolute sample position;
- active scene version;
- explicit scene/cue changes;
- manual control events.

At 48 kHz and 32-bit, 24 mono channels require approximately 4.6 MB/s or
16.6 GB/hour, which is comfortably within the target storage bandwidth.
Long recordings must use a container that safely supports their size, such as
RF64, with recoverable metadata.

## Offline review loop

Spectral and statistical analysis runs on Debian after rehearsal or performance,
never in the time-critical Buildroot audio path.

1. Record dry tracks, optional stems, master, and markers.
2. Split or address material by song and section.
3. Measure ordinary mix problems: mud, masking, rumble, harshness, peaks,
   dynamics, phase/correlation, vocal intelligibility, and inconsistent
   song-to-song levels.
4. Produce transparent recommendations with evidence and bounded parameter
   proposals.
5. Render loudness-matched virtual-soundcheck alternatives.
6. Let the operator approve, edit, or reject every proposal.
7. Store only approved settings in the versioned song scene.
8. Rehearse the resulting scene before live use.

Analysis can be computationally expensive because it is offline. It must not
claim that spectral overlap alone is a defect: recommendations must consider
the active section and the declared musical roles.

A recommendation is advisory data, not executable automation. It identifies the
song, section, source, observation, proposed change, limits, and evidence. Its
initial state is always unapproved.

## Conservative correction policy

Prefer, in order:

1. arrangement or source correction;
2. static level and EQ;
3. ordinary, explicitly configured compression;
4. shallow sidechain or frequency-selective dynamic correction only when the
   simpler choices cannot solve a demonstrated conflict.

Default analysis proposals should be deliberately bounded:

- no more than three EQ bands per channel;
- normally no more than +/-3 dB EQ change;
- no automatic sub-bass boost;
- no routing, monitor, or hardware-calibration changes;
- no activation without listening and approval.

These are proposal defaults, not hidden live limits.

## Sidechain policy

Sidechain processing is optional and postponed until recordings and virtual
soundcheck justify it. It is an explicitly configured per-song tool, never
source-detected or automatically enabled.

Likely valid uses are:

- gentle kick-versus-bass separation;
- lead vocal opening a narrow intelligibility band in a dense instrument group;
- vocal ducking only its own delay or reverb return.

Prefer frequency-selective dynamic EQ over full-band ducking. Typical maximum
gain reduction should be approximately 0.5-2 dB with gentle ratios and
material-appropriate attack/release. It passes review only when bypass makes
the mix subtly less clear while the enabled processor is not perceptible as
ducking or pumping.

Offline review should compare:

1. the current approved mix;
2. a static level/EQ proposal;
3. a shallow dynamic proposal.

If the dynamic version is audibly working or not clearly more natural, reject
it.

## Musical groups and DSP allocation

Groups are first-class mixer objects. They represent musical function rather
than automatically detected frequency ranges. The initial group vocabulary is
drums, bass, instruments, vocals, and effects returns, with explicit membership
stored per song. For example, bass may be a sampler input in one song and a
modular input in another. The live engine never classifies or moves it
automatically.

Processing is deliberately hierarchical:

1. inputs perform trim, polarity, high-pass filtering, mute, routing, and only
   source-specific corrective EQ or dynamics that are genuinely required;
2. musical groups perform broad tonal EQ, level control, and gentle compression;
3. groups feed the master, shared vocal effects, and explicit monitor mixes.

Offline analysis proposes corrections from broadest to narrowest: group
balance, broad group EQ, gentle group compression, individual-channel
correction, and only then shallow dynamic or sidechain treatment. This saves DSP
and produces controls and scenes that express musical intent.

Automatic frequency-band grouping and default multiband processing are outside
scope. Spectral measurements may inform an ordinary group EQ recommendation,
but they never create live routing, crossovers, or adaptive grouping.

The same explicit group model must drive song scenes, virtual soundcheck,
recording metadata, norns/virtual controls, and the later Studer Dyaxis II
surface.

## Implementation sequence

1. Prove the compiled-payload path and the tone/xrun test; physical evidence
   is limited to ADAT1 and ADAT2 on the installed main bracket, with ADAT3
   remaining software-path-only until its expansion bracket exists.
2. Implement a stable 24-channel pass-through mixer with metering and safe
   bypass.
3. Add dry multitrack recording, recoverable session metadata, and markers.
4. Add deterministic groups, monitor buses, and shared vocal sends.
5. Add versioned show baselines, song scenes, section cues, smooth recall, and
   rollback.
6. Add virtual soundcheck using the exact live mixer graph.
7. Add offline reports and A/B renders that never activate changes.
8. Consider bounded sidechain processing only from real rehearsal evidence.
9. Map the stable control model to a virtual surface, norns, and finally the
   Studer Dyaxis II controller.

## Acceptance principles

- A cold boot produces the same routing and sound for the same approved state.
- The system performs no unrequested or adaptive live action.
- Losing the analysis subsystem cannot affect the live engine.
- A failed or invalid scene cannot replace the current known-good scene.
- Recording failure is reported clearly and cannot silently disrupt live audio.
- Scene changes are click-free, bounded, observable, and reversible.
- All software-testable behaviour is automated; user work is limited to
  unavoidable listening, physical ADAT checks, and musical approval.
