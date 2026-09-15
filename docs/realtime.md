# Real-time strategy

Real-time tuning reduces worst-case scheduling delay and xruns. It does not make
a SynthDef compute faster. DSP throughput and scheduling determinism must be
measured separately.

Linux 6.12 and newer contain the mainline PREEMPT_RT infrastructure for x86.
The appliance must still set `CONFIG_PREEMPT_RT=y`; a recent kernel alone is
not sufficient.

The provisional fragment enables fully preemptible scheduling, 1000 Hz timers,
high-resolution timers, ALSA PCM, and the original DIGI9652 driver
`snd-rme9652`.

The eventual launcher should lock required memory, use an explicit bounded
real-time priority, place the RME IRQ above ordinary services, place Ethernet
control below audio, start at 48 kHz/128 samples, and stop clearly if the audio
device or clock is absent. Exact priorities remain unset until measured.

For every kernel, record its version, command line, preemption model, governor,
IRQ mapping, temperature, driver state, scheduling latency, xruns, and
SuperCollider DSP load. Compare the same workload and change one setting at a
time.

Do not pre-enable `isolcpus`, `nohz_full`, `rcu_nocbs`, forced IRQ affinity,
disabled C-states, unlimited RT runtime, or other folklore tuning. Those
choices depend on measured PCI routing, thermals, and latency.

## Docker JACK realtime operation

### Verified boundary

The Dockerized 26x26 JACK/scsynth service runs realtime by default. The
Compose service explicitly requests `IPC_LOCK` and `SYS_NICE`, `memlock=-1`,
and `rtprio=95`. The host Docker service is rootful and has
`LimitMEMLOCK=infinity`, `LimitRTPRIO=95`, `LimitNICE=0`, and
`NoNewPrivileges=no`. The live container receives both capabilities, unlimited
memlock, and `rtprio=95`; its memory cgroup is unlimited.

Direct probes succeeded in both host and container for one-page `mlock`,
`mlockall(MCL_CURRENT|MCL_FUTURE)`, and `SCHED_FIFO`. JACK then started with
realtime priority 70 and scsynth reported `SuperCollider 3 server ready`.
Therefore no systemd, kernel, GRUB, privileged-mode, or global security change
is required. The earlier `ENOMEM` was not reproducible under the verified
current boundary and is not hidden by falling back to non-realtime mode.

## Verification

Run:

```sh
./scripts/sc-audio build
./scripts/sc-audio start
./scripts/test-sc-audio
```

The test defaults to 600 seconds and records the JACK/scsynth status, JACK
thread scheduling, port counts, xrun counts, and service logs in
`.local/sc-audio-reports/`. Relevant kernel messages can be reviewed with:

```sh
journalctl -k -b --no-pager | grep -iE 'xrun|snd|rme9652|oom|apparmor|denied'
```

## Rollback

The reversible runtime rollback is:

```sh
JACK_REALTIME=0 ./scripts/sc-audio start
```

To restore realtime, recreate the service without the override:

```sh
docker compose -f containers/sc-development/compose.yaml down
./scripts/sc-audio start
```
