# Stereo and quad group mixers

The Debian/Docker group mixers run at 48 kHz and 128 frames. Sixteen hardware
inputs are processed and assigned to eight canonical groups. The default
`./lab mixer start` path is stereo and emits only to outputs 1–2;
`./lab mixer-quad start` is an independent quad program and emits only to
outputs 1–4 in FL, FR, RL, RR order. Neither program provides transparent
16-input-to-16-output routing; separate hardware/tone/sample-flow diagnostic
tools remain available.

`supercollider/synthdefs/sc-adat-mixer.scd` contains the DSP authority. The
versioned scene and `mixer/mixerctl.py` currently provide a Debian/Docker
development and validation harness for configuration, validated OSC
forwarding, node startup and bounded meter reception. That Python harness is
not the production live control path or authoritative mixer state and MUST NOT
be required by the Buildroot appliance. The DSP has eight canonical groups
matching the Dyaxis faders: kick, drums, bass, music_a, music_b, vocals, fx_a,
and fx_b.
Stereo is the production default. The two programs are started and stopped
independently; the launcher refuses to start one while the other is running.
JACK owns future hardware remapping.

Quad panning uses square-root bilinear rectangular weights, so squared gains
sum to one at every XY coordinate. Public X is 0 left/0.5 centre/1 right and
public Y is 0 rear/0.5 centre/1 front; the reusable group node converts this to
internal X/Y corners (-1,+1) front-left, (+1,+1) front-right, (-1,-1)
rear-left, (+1,-1) rear-right.
Spatial controls and calibration are smoothed over the 30 ms default.
Spatial bypass means a smoothed transition to neutral centre `(0.5, 0.5)`.
Output calibration and delay are deferred.

The existing scene has group membership but no authoritative stereo-pair
metadata. Quad mode uses the smallest deterministic fallback: each group's
existing mono sum is duplicated into two correlated components around the group
position, separated by width and power-normalized. It cannot recover
independent stereo information absent from the current topology.

Controls are smoothed over 30 ms. Gains are bounded, audio is clipped before a
short hard limiter, and invalid control values are rejected. The default scene
is unity, unmuted, normal polarity, HPF disabled, no sends, and no EQ or
compression. Meter reports are emitted at 10 Hz for 16 inputs, eight groups,
and 16 outputs.

The capture contract reserves stable physical identity: all 16 raw inputs are
captured pre-fader and pre-processing; eight pre-spatial group stems are
available by canonical name; and four post-spatial quad master channels are
available in canonical output order. Timestamped OSC automation and song
markers are metadata interfaces, not audio buses. Song scenes may reassign
stable physical inputs to functional groups. Recording is out of scope for
this milestone; these names are reserved so a recorder can be added later
without redesigning the mixer.

Use:

```sh
./lab mixer build
./lab mixer start
./lab mixer status
./lab mixer test
./lab mixer stop
```

The controller listens on UDP 57120 for `/mixer/set`, `/mixer/get`, and bounded
`/mixer/get-all`, forwards only validated changes to scsynth on UDP 57110, and
reports `/mixer/ok`, `/mixer/error`, `/mixer/state`, and a completion marker.

The runtime node graph is deterministic:

```text
In.ar(26,16) -> sc_adat_router (3900)
                 -> eight sc_adat_group instances (4000..4007)
                 -> selected fixed master (4100) -> outputs 1–2 or 1–4
```

The controller owns these transient IDs; clients address only logical group
IDs. The router preserves the 16 raw pre-processing inputs and produces eight
group-stem buses. Every group uses the same reusable `sc_adat_group` SynthDef.
The master meters all 16 raw inputs, eight group stems, and the actual 16
post-protection output channels at 10 Hz. Startup/restart frees the owned graph,
recreates it under one node group, and synchronizes SynthDef loading first.

Spatial envelopes are mixer-enforced: kick and bass are front-centre; drums
and vocals are front-biased; music_a/music_b have broad movement; fx_a/fx_b
have the full quad field. Each has an explicit neutral position in the scene.

Clock ownership belongs to the Debian audio-hardware layer. `./lab audio clock
status|set ...` addresses ALSA by the stable `Digi9652` name, and `./lab mixer
clock ...` is only a compatibility delegation. The declarative default is
`audio/clock.conf` (`mode=autosync`, `source=adat1`, `sample_rate=48000`).
Mixer startup performs a read-only preflight and requires the selected external
source to be locked before JACK starts; it never applies Master implicitly.
Explicit `scripts/audio-clock set|apply` commands remain available for deliberate
clock changes while JACK is stopped. The later Buildroot integration point is
the audio init service immediately after Digi9652 detection and before `jackd`,
using a native equivalent of this preflight and explicit clock policy; Buildroot
is not changed by this milestone.

Implemented now: 16-input group processing, versioned neutral configuration,
smoothed controls, spatial bypass, protection, OSC control and query, meters,
payload compilation, load/sync checks, and Docker dummy-JACK integration.

Deliberately deferred: recording, song markers, scenes per song, EQ,
compression, sends, offline analysis, virtual soundcheck, and Dyaxis control.
Private buses are disjoint: hardware inputs `26..51`, group stems `52..59`,
and reusable-group quad outputs `76..107`; physical outputs use `0..25`. The
master transposes the group-major 8×4 layout: speaker
`s` is `sum(group[s + 4*g] for g=0..7)`. The canonical speaker vector is
front-left, front-right, rear-left, rear-right. Public Y remains `0` rear,
`0.5` centre, `1` front.

The quad master emits the canonical FL, FR, RL, RR tuple directly at bus zero.
The stereo master folds front/rear pairs while retaining left/right position.
Both apply bounded `clip2(4)` and `Limiter.ar(..., 0.99, 0.01)` before output
and meter calculation. Outputs unused by the selected master remain silent.

On the validated target scsynth build, a runtime control-rate bus selector used
as `Out.ar`'s destination is not reliable: a direct pass-through probe writes
no signal. The reusable group SynthDef therefore writes all eight fixed
four-channel lanes and gates exactly one tuple with its validated integer
`groupIndex`. This preserves one SynthDef and independent ownership while
avoiding feedback, latency, or per-group SynthDef duplication. The lane map is
group 0=`76..79`, group 1=`80..83`, through group 7=`104..107`.

The scan fixture uses `Env.asr(0.05, 1, 0.10, doneAction: 2)`: gate zero starts
a 100 ms release and `doneAction: 2` frees the scan node when that envelope
completes. Tests use a unique scan ID, send gate zero, poll through the intended
release, explicitly `/n_free` as bounded cleanup, `/sync`, and prove absence
with `/n_query`. The meter peak and RMS paths each decay over 100 ms. Before
and after every case, the fixture requires four consecutive 10 Hz meter frames
with every relevant output below the strict `0.01` threshold; the timeout
reports node tree, effective controls, and peak/RMS history. This identifies
the former corner residue as stale scan-fixture energy, not spatial leakage.
