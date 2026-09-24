# SC-ADAT Chataigne control project

This is an optional Chataigne control surface for the committed SC-ADAT OSC
contract. It does not process audio, start the mixer, alter SuperCollider, or
replace mixer-side validation. The Dell controller remains authoritative.

## Version and seed

The installed application is Chataigne 1.10.4 on macOS. The repository's
authoritative seed is `../../chataigne/Mixer.noisette`; it is readable JSON and
contains the 1.10.4 metadata and `OSC` module serialization used by the
generated project. The requested historical path
`control/chataigne/sc-adat-quad.noisette` did not exist in the checkout; this
directory is the new canonical location.

Generate the project from the seed with:

```sh
python3 tools/generate_chataigne_project.py
```

Open `control/chataigne/sc-adat-quad.noisette` in Chataigne 1.10.4. The Dell
host is one editable OSC output setting, `remoteHost`, defaulting to
`192.168.1.100` as a placeholder; replace it with the currently configured Dell
address. `remotePort` defaults to `57120`.

## Contract and controls

The exact supported writable messages are listed in
`reference/controls.json`. They use `/mixer/set` with OSC signature `,sf` and
the parameter key as the string argument. Refresh uses `/mixer/get-all` with no
arguments; state, ok, error and get-all-done replies are shown by the script
logic in `scripts/sc_adat_mixer.js`.

The eight equal group panels are: kick (0), drums (1), bass (2), music_a (3),
music_b (4), vocals (5), fx_a (6), and fx_b (7). Each supported panel has
level, X, Y, width, spatial bypass and neutral/reset actions. Group mute is
not advertised because the committed controller has no confirmed writable
`groupNMute` key; it remains a deliberately disabled placeholder. FX A and FX
B are not renamed or treated as utility effects.

Quad output calibration is separate from performance controls: front-left,
front-right, rear-left and rear-right each expose gain, mute and polarity.
Calibration is setup-only and must be explicitly armed. Parrot gesture capture
and Time Machine sequences are placeholders and never arm on load or connect.
Stop Automation is the global emergency action and returns automation to the
current manual state without sending a movement merely because the project
opened.

## Operation

1. Open the `.noisette` project in Chataigne 1.10.4.
2. Set `remoteHost` once to the Dell address; leave `remotePort` at `57120`.
3. Use explicit Connect/Refresh to send `/mixer/get-all`; connection is state
   synchronization only.
4. Operate the eight group panels manually. The mixer enforces spatial limits.
5. Arm automation explicitly before using Parrot or Time Machine, and use Stop
   Automation to return to manual/current state.
6. If state becomes stale, stop automation, verify the Dell address and refresh.

For no-audio verification, run the mixer OSC tests or observe `/mixer/state`,
`/mixer/ok`, `/mixer/error` and `/mixer/get-all-done` packets with a UDP test
listener. Chataigne is not required for mixer startup or audio recovery.

The readable script is kept outside the packed project where Chataigne permits
it. It is the reference for exact message construction and incoming-state
handling; attach it to the OSC module's script slot if this Chataigne build
does not automatically discover project-local scripts. No automatic movement
or feedback loop is permitted.

The current Dell quad-graph repair is separate and may change which already
documented controls are effective. No proposed API addition is implemented.
