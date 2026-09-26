# SC-ADAT Chataigne control surface

This is an optional external control client. It does not process audio, start
the mixer, alter SuperCollider, or replace mixer-side validation. Chataigne is
never required for appliance startup.

## Production runtime boundary

Chataigne MUST remain optional. Normal stereo live mode MUST work without this
project, Python, a Mac, a web interface, an automation engine, or a network.
Chataigne is for rehearsal, experimentation, OSC/XY authoring, attended quad
movement, and explicitly armed automation. If it disconnects or closes,
SuperCollider MUST continue unchanged from its last valid state. Chataigne
cannot become the boot, audio, safety, or authoritative state layer.

## Version and generation

The project was generated from `../../chataigne/Mixer.noisette`, the readable
seed for the installed Chataigne 1.10.4 (`versionNumber` 68100). The generator
uses the installed-version native serialization for Custom Variables,
Point2D dashboard controls, dashboard groups and project-local scripts:

```sh
python3 tools/generate_chataigne_project.py
```

Open `sc-adat-quad.noisette` in Chataigne 1.10.4. The script is attached to
the OSC module at `scripts/sc_adat_mixer.js`; it is kept readable and separate
from the packed project. Reopen the generated file after generation to verify
the native dashboard collection.

## Network and synchronization

The OSC output has one editable `remoteHost` setting, defaulting to
`192.168.1.100`, and UDP port `57120`. Change the host once in the OSC output;
there are no duplicated addresses in dashboard mappings. `Connect / Refresh`
sends only `/mixer/get-all` and does not write mixer state. Opening the project
does not send `/mixer/set` or begin automation.

The script applies incoming `/mixer/state` to the native Custom Variables
under a feedback guard, so remote state updates the dashboard without an OSC
feedback loop. `/mixer/ok`, `/mixer/get-all-done` and `/mixer/error` update the
visible status. A stale/error status never changes mixer state automatically.

## Dashboard

The `SC-ADAT Groups` dashboard contains eight native `DashboardGroupItem`
panels, all visible in the same dashboard and identified as:

| ID | Group |
|---:|---|
| 0 | kick |
| 1 | drums |
| 2 | bass |
| 3 | music_a |
| 4 | music_b |
| 5 | vocals |
| 6 | fx_a |
| 7 | fx_b |

Each panel has a level fader, native Point2D XY canvas, width, spatial bypass
and Neutral reset. The committed API has no confirmed writable group-mute key,
so group mute is intentionally absent. XY uses X 0=left/1=right and
Y 0=rear/1=front; the Dell remains authoritative for constraints.

`Connection and Safety` contains connection state, Refresh, explicit
automation arm and the global Stop Automation action. Stop Automation invokes
the installed Chataigne Parrot stop triggers and Time Machine `stopAll` trigger;
it is not merely a private flag. Parrot and Time Machine remain placeholders
until a user explicitly arms automation.

`Quad Output Calibration (armed)` is separate from performance controls.
Front-left, front-right, rear-left and rear-right each expose gain, mute and
polarity. Changes are transmitted only while Arm Calibration is active.
`routingMode` is displayed as read-only status and is not a writable control.

## Supported OSC

Outgoing performance and armed calibration changes use exactly:

```text
/mixer/set ,sf <parameter-key> <float-value>
/mixer/get ,s <parameter-key>
/mixer/get-all
```

The exact supported keys are in `reference/controls.json`. Bulk state replies
use the versioned `/mixer/state-chunk` protocol and must be reassembled by
snapshot/chunk metadata; `/mixer/get-all-done` is no longer a per-entry stream
marker. There is no
unimplemented API addition in this project. Incoming `/mixer/state`,
`/mixer/ok`, `/mixer/error` and `/mixer/get-all-done` are handled by the
attached script.

## Mock and operation

Run the dependency-free mock receiver on a development machine:

```sh
python3 tools/chataigne_mock_osc.py --host 127.0.0.1 --port 57120
```

Set `remoteHost` to `127.0.0.1`, press Connect / Refresh, and observe the
validated packets. This can be done with no speakers connected. Restore the
Dell host before live use. A stale/error state is recovered by checking the
host and pressing Refresh; Chataigne does not attempt automatic recovery
writes.

For rehearsal and authoring, use the eight group panels and arm calibration
before touching output setup. Arm Parrot or Time Machine explicitly, and use
Stop Automation to stop playback and retain current values. Normal stereo
performance uses the reviewed SuperCollider program without requiring this
client; the Dell/SC runtime remains the safety authority.

## Validation and limitations

The project has been reopened in the installed Chataigne 1.10.4 and its
normalized dashboard serialization inspected. Host tests validate the OSC
mock, all eight group key families, Refresh, malformed/error handling and the
absence of writable `routingMode`.

The mock proves packet construction and state-model behavior without hardware;
it is not a substitute for a live Dell run. One real dashboard gesture and a
live incoming state update should still be observed with the mock receiver
after any local Chataigne UI layout changes. The separate Dell quad-graph
repair remains outside this project.
