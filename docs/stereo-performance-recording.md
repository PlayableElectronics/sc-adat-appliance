# Stereo performance and recording preparation

This work targets the current stereo live mixer. Live RME/JACK capture and
scsynth-to-PA playback remain the priority. Quad rendering is preserved; its
existing `sc_adat_group` SynthDef is unchanged. New group processing is in the
separate reusable `sc_adat_stereo_group` SynthDef. Nothing here was deployed or
physically validated on the Dell.

## Signal and recording boundary

The standalone `sc-adat-recorder` JACK client connects to the same upstream
JACK capture ports as the mixer, before any appliance source or group DSP. It
copies 17 physical capture ports (inputs 1--16 plus analog sync on 17) and the
two final `jack:out_1/2` master ports into a bounded single-producer/single-
consumer ring. Its JACK callback performs no filesystem calls; one writer
thread splits complete frames into libsndfile WAV tracks. It does not connect
to scsynth controls and cannot restart or change JACK/scsynth/RME configuration.
Queue exhaustion or disk errors stop only recording and are exposed in status.

WAVs are 48 kHz, PCM-24. The authoritative `source_map` generates one mono WAV
per mono source and one interleaved stereo WAV per ordered stereo pair (left,
right in map order), named from the stable source ID. `sync.wav` is mono input
17 and `master.wav` is stereo, post-processing/post-limiter. Optional ALSA
sequencer capture writes a standard MIDI file `events.mid` when
`recording.midi_port` is configured; an unavailable MIDI port is reported but
does not stop audio recording.

Every recording start creates a UTC timestamp plus random-ID directory with
`session.json`, `tracks.tsv`, and `segment-NNN/`. Segments default to 900 s.
The writer finalizes the current segment before opening another. It opens a
next segment only with enough space for the full 19-channel segment plus the
configured 5 GiB reserve. It stops cleanly at the reserve threshold. No session
is appended to or deleted automatically.

Production safety requires `/recordings` to be a writable ext4 mount with the
configured filesystem UUID. Empty UUID, missing/wrong mount, read-only mount,
or less than two hours of capacity prevents start; there is no fallback path.
The expected consumption is 2,736,000 bytes/s (19 channels × 48,000 × 3),
about 9.85 GB/hour before filesystem overhead. Configure the dedicated SSD UUID
in `/etc/sc-adat/recording.conf`; the checked-in empty value intentionally
leaves recording unavailable until configured.

OSC `recordStart=1` and `recordStop=1` extend the existing authoritative
`/mixer/set ,sf` control contract. Read-only `recorder*` values report state,
elapsed time, segment, estimated time remaining, free bytes, dropped frames,
and error. Recording never starts at boot. The Python code is control/session
management only; it is not in the audio-data path.

## Stereo group and master controls

Each of eight existing reusable group nodes has neutral-by-default, separately
bypassable four-band EQ (low/high shelves and two peaking bands; band
frequencies and gains are bounded), linked stereo compression, and bounded
tanh saturation. Group gain/mute and established source trim, polarity, HPF,
pan/balance/width and grouping remain. Group DSP bypasses are enabled by
default; compressor and saturation are bypassed; duck amount is 0 dB. The kick
detector reads the post-source-conditioning kick stem before group processing.
Each group can set duck depth (0--18 dB), linear threshold, attack and release.
The normal compressor and ducking are independent.

Stereo master processing preserves its existing attenuation and safety limiter;
it adds a neutral broad peaking EQ with true bypass and panic mute after the
limiter. The test generator has an explicit 10-second arm followed by enable,
a -40 dBFS default and a -30 dBFS hard cap, selected group destination,
pink-noise/1 kHz/left-right-identification modes, and a 30-second auto-stop.
It enters the group path and remains under the master limiter and panic mute.
It is never created on project/mixer startup.

The control schema `control/mixer-control-contract.json` is authoritative.
`./lab control generate norns` regenerates both exported mixer schema and the
Norns Lua reflection; the generated Norns control inventory is not maintained
by hand. Norns remains the primary mixer UI. Chataigne integration is on hold
and was not expanded as part of this work.

Local reproducible checks are `./scripts/test-control-contract`,
`python3 -m unittest mixer.test_recorder_policy mixer.test_stereo_dsp_contract`,
and `cc -std=c11 -Wall -Wextra -Werror $(pkg-config --cflags jack sndfile)
package/sc-adat-recorder/sc-adat-recorder.c $(pkg-config --libs jack sndfile)
-pthread`. The full `./scripts/test-mixer` additionally compiles SuperCollider
SynthDefs and runs dummy-JACK/scsynth integration in Docker; it requires the
project image and a working Docker daemon.

## Buildroot preparation

`package/sc-adat-recorder` prepares target-native JACK/libsndfile capture plus
Python control-plane modules, ALSA utilities for optional `arecordmidi`, and
the contract file. `board/dell-optiplex-7010/buildroot.config` selects these
dependencies. No Buildroot build, image stage, GRUB change, slot write, boot,
or deployment was performed here. Production remains planned as read-only
Buildroot `/`, tmpfs `/run`, `/tmp`, bounded `/var/log`, and only the dedicated
external SSD at `/recordings`.

## Physical acceptance tests still required

- Confirm SSD UUID, ext4 mount, writability, and wrong/read-only mount refusal.
- Sustain all 19 captured audio channels longer than a concert and measure disk
  throughput and xrun/drop counters.
- Kill the recorder while PA passes; remove SSD while PA passes; simulate full
  disk and power loss; confirm only recording stops/fails.
- Verify all source playback, pre-FX tracks, final master reference, sync pulse,
  and optional ALSA MIDI file.
- Rehearse with zero xruns and test in the closed rack at operating temperature.
- Measure neutral bypass, EQ, compressor, saturation, kick-duck depth/attack/
  release, limiter and panic mute using real scsynth/JACK and the RME.
- Verify generator cap, auto-stop, selected destination, limiter and panic mute.
- Confirm ADAT clock-loss reporting remains read-only during normal startup.

No physical acceptance item above is claimed as passed.
