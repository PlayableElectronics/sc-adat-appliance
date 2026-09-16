# Production mixer milestone

The Debian/Docker mixer is a transparent 16-channel hardware path at 48 kHz,
128 frames, with one-to-one `system:capture_1..16` to
`system:playback_1..16` processing. Channels 17..26 remain unused. The data
model reserves 24 channels, but the validator rejects physical mappings above
16 until those inputs are confirmed.

`supercollider/synthdefs/sc-adat-mixer.scd` contains DSP only. The versioned
scene in `payload/config/mixer.conf` and `mixer/mixerctl.py` own configuration,
validation, OSC policy, node startup, and bounded meter reception. The DSP has
five explicit groups: drums, bass, instruments, vocals, and fx_returns.

Controls are smoothed over 30 ms. Gains are bounded, audio is clipped before a
short hard limiter, and invalid control values are rejected. The default scene
is unity, unmuted, normal polarity, HPF disabled, no sends, and no EQ or
compression. Meter reports are emitted at 10 Hz for 16 inputs, five groups,
and 16 outputs.

Use:

```sh
./lab mixer build
./lab mixer start
./lab mixer status
./lab mixer test
./lab mixer stop
```

The controller listens on UDP 57120 for `/mixer/set` and `/mixer/get`, forwards
validated changes to scsynth on UDP 57110, and reports `/mixer/ok`,
`/mixer/error`, and `/mixer/state`.

Implemented now: transparent 16-channel routing, explicit groups, versioned
neutral configuration, smoothed controls, bypass, protection, OSC control and
query, meters, payload compilation, load/sync checks, and Docker dummy-JACK
integration.

Deliberately deferred: recording, song markers, scenes per song, EQ,
compression, sends, offline analysis, virtual soundcheck, and Dyaxis control.
