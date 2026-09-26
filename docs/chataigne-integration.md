# Chataigne integration

## Relationship to the Production Runtime Boundary

Chataigne is an optional external creative controller, never a production
runtime authority. It MUST NOT be required to boot, start audio, enforce
safety, restore normal stereo state, or keep SuperCollider running. Normal
stereo performance MUST continue headlessly if Chataigne closes or the network
disappears; SuperCollider retains the last valid state. Chataigne is intended
for rehearsal, experimentation, OSC/XY control, quad movement authoring, and
explicitly armed automation. Python is not a live control dependency; it is
reserved for offline/development analysis and diagnostics.

Chataigne is optional show control and dashboard software. It does not process
audio and mixer startup and DSP smoothing must not depend on it. The Dell
controller listens on UDP port **57120**.

The versioned control interface is defined by
`control/mixer-control-contract.json`. Chataigne reference metadata is checked
against that contract, including its version and group keys, so it must not
define conflicting control identities, ranges, or modes.

The eight group IDs are `0 kick`, `1 drums`, `2 bass`, `3 music_a`, `4 music_b`,
`5 vocals`, `6 fx_a`, and `7 fx_b`. Coordinates are normalized: X `0` left, `0.5` centre, `1`
right; Y `0` rear, `0.5` centre, `1` front.

| Message | OSC signature | Meaning |
|---|---|---|
| `/mixer/set` | `,sf parameter value` | validated finite update |
| `/mixer/get` | `,s parameter` | one `/mixer/state` reply |
| `/mixer/get-all` | no arguments | chunked state snapshot, then `/mixer/state-complete ,sii snapshot chunks entries` |

Spatial parameters are `groupNPosX`, `groupNPosY`, `groupNWidth` and
`groupNSpatialBypass` (`N=0..7`). Calibration parameters are
`quadOutputNGainDb`, `quadOutputNMute` and `quadOutputNPolarity` (`N=0..3`),
in order front-left, front-right, rear-left, rear-right. Replies are
`/mixer/ok ,s parameter`, `/mixer/error ,s reason`, and
`/mixer/state ,sf parameter value` (routing mode uses `,ss`). Bulk clients use
`/mixer/state-chunk ,sii...` with a snapshot ID and bounded typed key/value
pairs; the contract defines the complete bulk-state format.

The established `/mixer/set` keys are the semantic compatibility surface:
`groupNPosX/Y` is group position, `groupNWidth` is width, and
`groupNSpatialBypass` is spatial bypass. These eight logical IDs are the only public
group identity; transient scsynth node IDs are never exposed.

Use 30–60 Hz for coordinate updates. DSP smoothing remains authoritative;
Chataigne should not add a second audio automation layer. Initial mappings are
Manual control for XY/width, Parrot for an explicitly armed live gesture
source, and Time Machine for recalled parameter snapshots or show cues.
Automation must be explicitly enabled by the operator; a connection never
implicitly enables it.

The `master` control is the global output gain. Stereo and quad are independent
programs selected by their launch commands; there is no runtime routing mode or
transparent direct mode in either group mixer.
Spatial bypass is a smoothed transition to neutral centre `(0.5, 0.5)`.
