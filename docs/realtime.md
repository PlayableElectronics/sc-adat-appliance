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

Do not pre-enable `isolcpus`, `nohz_full`, `rcu_nocbs`, forced IRQ
affinity, disabled C-states, unlimited RT runtime, or other folklore tuning.
Those choices depend on measured PCI routing, thermals, and latency.
