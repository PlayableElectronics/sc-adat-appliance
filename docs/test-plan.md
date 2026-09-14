# Initial test plan

## Hardware baseline

Run `scripts/collect-hardware-baseline` from Debian and save its output outside
Git. Review it for identifiers before committing selected facts to
`docs/hardware-baseline.md`.

## Audio baseline

Start at 48 kHz and a 128-sample buffer. Verify card detection, clock lock,
channel order, silence, sustained multichannel playback, xruns, and recovery
after restarting the audio process.

Test 64 samples only after the 128-sample baseline is stable.

## Real-time comparison

Measure the same workload under the same sample rate and buffer size:

1. Debian distribution kernel.
2. Debian real-time kernel or explicitly configured PREEMPT_RT kernel.
3. Buildroot appliance kernel.

Record worst-case latency, xruns, DSP load, temperature, and relevant kernel
configuration. Change one tuning parameter at a time.
