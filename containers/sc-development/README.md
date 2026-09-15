# SuperCollider development container

This is the hardware-facing Debian staging environment for the first audio
milestone. It runs JACK and `scsynth` natively in the container while the host
provides only `/dev/snd` and the verified RME hardware.

Build and control it from the repository root:

```sh
./scripts/sc-audio build
./scripts/sc-audio start
./scripts/sc-audio status
./scripts/sc-audio test
./scripts/sc-audio logs
./scripts/sc-audio stop
```

Realtime JACK is the default. The Compose file carries `IPC_LOCK`, `SYS_NICE`,
unlimited memlock, `rtprio=95`, and a 256 MiB `/dev/shm`. For a deliberate
diagnostic comparison, run with `JACK_REALTIME=0`; this is not the validated
audio mode.

The image uses a digest-pinned Debian 13 base and the Debian packages
`jackd2`, `jack-example-tools`, `supercollider-server`, `alsa-utils`, and
diagnostic utilities. The validated image currently contains SuperCollider
3.13.0 and JACK 1.9.22.
