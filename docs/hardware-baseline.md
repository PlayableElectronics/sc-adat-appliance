# Verified hardware baseline

This note records only reusable hardware facts; machine-specific identifiers
and generated reports remain outside Git.

- Target: Dell OptiPlex 7010, Intel Core i7-3770S, Debian 13.
- Audio interface: original RME DIGI9652, PCI driver `snd-rme9652`.
- PCI location: `02:02.0`; PCI ID `10ee:3fc4`; revision `03`.
- ALSA device: `hw:CARD=Digi9652,DEV=0`.
- Verified format: 26-channel, 48 kHz, `S32_LE` playback.
- Native hardware access: non-interleaved.
- Minimum reported period: 64 frames.
- Current IRQ: 18, shared with `i801_smbus`.

The Docker/JACK milestone uses 48 kHz, 128 frames, 2 periods, and 26 capture
and 26 playback channels. The host kernel is Debian 6.12.107 with
`PREEMPT_DYNAMIC`; realtime kernel tuning remains outside this milestone.
