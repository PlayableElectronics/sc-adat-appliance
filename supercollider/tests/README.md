# SuperCollider validation workloads

Tests must report sample rate, block size, server implementation, output count,
SynthDef revision, duration, xruns, peak DSP, and average DSP.

Planned cases:

1. silent 24-channel routing;
2. one oscillator per ADAT channel for channel-order validation;
3. repeatable modal-bank CPU load;
4. parallel voice groups for `supernova`;
5. OSC burst and sustained-control tests;
6. controlled overload and recovery.

Audio-generating tests must start muted or at a conservative level and require
an explicit output enable.
