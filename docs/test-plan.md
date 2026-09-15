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

## Pre-release staging

### Debian userspace stage

Run the versioned scsynth/supernova build and its exact plugins from a clean
staging prefix. Use the real DIGI9652 and the standard audio workload. Record
the release ID, executable/library hashes, kernel, buffer, channel count,
clock state, xruns and DSP load.

This is the fast edit/build/test loop. It does not validate the Buildroot
kernel, init sequence or RAM-root filesystem.

### One-shot GRUB candidate

Before writing slot A or B, copy the versioned release bundle to a candidate
directory on Debian storage and create a temporary, non-default GRUB entry.
Boot its exact kernel and initramfs/RAM-root image.

Verify:

1. no appliance slot was written;
2. root is read-only or RAM-backed as designed;
3. transient paths use tmpfs;
4. persistent data mounts only at the intended location;
5. `snd-rme9652` loads and all three ADAT banks work;
6. scsynth and control services start and recover correctly;
7. Dyaxis Nano USB-serial input works;
8. OSC control works over wired Ethernet;
9. Debian and the known-good slot remain selectable;
10. manifest hashes equal the candidate files.

Only the exact bundle that passed this test may be deployed to an inactive
slot.
