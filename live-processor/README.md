# ADAT live processor foundation

This package is a native, deterministic live processor, not an offline mastering
tool and not an extension of the SuperCollider mixer. It accepts eight physical
input channels and produces stereo at exactly 48 kHz. The Yamaha AW2816 remains
responsible for source level and headroom. There is no automatic gain, loudness
normalization, EQ matching, width correction, reference matching, classification,
or adaptive mixing.

## Fixed channel contract

| Physical inputs | Role | Core treatment |
|---|---|---|
| 1 | kick, mono | centre, equal-power pan |
| 2 | bass, mono | centre, equal-power pan |
| 3–4 | drums, stereo | preserve L/R order |
| 5–6 | synths/music, stereo | preserve L/R order |
| 7–8 | vocal loops/FX, stereo | preserve L/R order |

Mono uses `1/sqrt(2)` gain to each side, giving unit total power across stereo.
Stereo pairs pass at unity. All five roles sum. Trims default to unity. The
optional `--bypass` path routes mono inputs at unity to both sides and stereo
pairs directly, ignoring role and master trims; it is a path bypass, not a
level-matched bypass. No compressor, EQ, saturation, limiter, bloom, or signature
processing is present.

## Real-time and live adapter behavior

`Processor::process_block` takes interleaved `8 * frames` input and `2 * frames`
output slices. Maximum block size is chosen at construction. It allocates no
memory and performs no file I/O, logging, locking, or blocking. Buffers are
length-checked, non-finite input is counted by role and replaced with zero, and
non-finite output is counted and replaced with zero. The callback publishes
individual atomic meter fields without locks; a snapshot is race-free per field
but can combine values from adjacent callback updates.

CPAL is the live layer, using CoreAudio on macOS and ALSA on Linux; JACK is not
required. The selected single device must advertise f32 input with at least
eight channels and f32 output with at least two channels, both at exactly
48 kHz. This full-duplex, single-device requirement also provides the clock
source. Device channel indices shown to users are 1-based and follow the host's
advertised interleaved channel ordering. The selected channel list is mapped in
the fixed role order above. The implementation requires f32 configurations and
fails clearly if unavailable; it does not silently use another device, rate, or
layout.

Input and output callbacks are decoupled by a preallocated `rtrb` SPSC ring of
`max(4 * requested frames, 256)` eight-channel frames. This represents about
5.33 ms at the 256-frame floor, or four requested callbacks above that. This is
the ring's capacity, not a claim that the live path always incurs that latency;
occupancy is workload-dependent. Input overflow drops newest frames. Output
underflow inserts zero frames. DSP runs in the output callback using scratch
buffers allocated before stream start. Requested callback buffers are 64 or 128
frames; host/device behavior must be measured to establish actual latency.
Diagnostics include callback-size discontinuities, ring overflow/underflow,
largest measured DSP duration, selected config, and nominal ring capacity.

## Meters

Role peak is the maximum absolute sample in the latest processed block. Peak
hold is the maximum since reset. Short RMS uses a 300 ms one-pole energy time
constant (`alpha = exp(-1/(sample_rate * 0.300))`); stereo role RMS averages the
two channel energies. Crest is current block peak divided by smoothed RMS.
Headroom is `-20 log10(peak)` dBFS, with infinity at silence. Over means a
role input peak is at or above 1.0. Stereo balance is `(Rpeak-Lpeak)/(Rpeak+Lpeak)`
for the latest block; correlation is the smoothed cross moment divided by the
smoothed L/R RMS product. Output meters expose L/R peak, RMS, clipping frames,
and invalid samples. Target structures are deliberately placeholders; the
Yamaha rehearsal capture will establish the role windows before signature DSP
is designed.

## Commands

From this directory:

```sh
cargo run -- list-devices
cargo run -- inspect-device 0
cargo run -- run --device 0 --buffer 128 --inputs 1,2,3,4,5,6,7,8 --outputs 1,2
cargo run -- run --device 'Exact Device Name' --buffer 64 --master-trim 0.8 --bypass
cargo run -- validate-config --config examples/live-processor.toml
cargo run -- process-wav kick.wav bass.wav drums-l.wav drums-r.wav synth-l.wav synth-r.wav vocal-l.wav vocal-r.wav --output mix.wav --block 128
```

The recording harness is only for repeatable development and tuning. It requires
eight aligned mono 48 kHz WAV files of identical length and runs those samples
through the same `Processor::process_block` core as live playback. No musical
reference recordings are included.

## Configuration and current limits

Config version 1 contains channel mapping, five role trims, master trim, buffer
size, and named placeholder meter target windows. No adaptive controls exist.
See `examples/live-processor.toml`. Device enumeration/inspection and startup
configuration validation happen before stream playback.

The initial DSP is only transparent summing. This milestone has not established
physical multichannel stability or low-latency performance. Hardware opening
depends on a full-duplex 8-in/2-out device that advertises the exact format.
Next, use the Yamaha rehearsal capture to establish role meter windows and then
design role-specific signature DSP with explicit fixed parameters.
