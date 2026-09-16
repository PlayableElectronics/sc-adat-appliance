# Real ADAT output testing

The SC-ADAT candidate uses the original RME DIGI9652 and Linux
`snd-rme9652`. The driver exposes ALSA/JACK playback channels in numeric order:
JACK `system:playback_1` through `_8` are ADAT1, `_9` through `_16` are ADAT2,
and `_17` through `_24` are ADAT3. `_25` and `_26` are the reserved S/PDIF
pair and are never connected by the tone test. Confirm the live order with
`sc-adat-jack-probe`, `aplay -D hw:CARD=Digi9652,DEV=0 --dump-hw-params`, and
the captured `/var/log/sc-adat-boot-report.log` before optical testing.

| ADAT bank | channel / JACK output | frequency |
|---|---:|---:|
| ADAT1 | 1–8 | 200, 250, 300, 350, 400, 450, 500, 550 Hz |
| ADAT2 | 9–16 | 600, 650, 700, 750, 800, 850, 900, 950 Hz |
| ADAT3 | 17–24 | 1000, 1050, 1100, 1150, 1200, 1250, 1300, 1350 Hz |

Connect three known-good optical cables from DIGI9652 ADAT outputs 1–3 to
three powered, clock-compatible optical receivers. Do not connect or monitor
the S/PDIF outputs 25–26 for this test.

Hardware inventory and historical acceptance evidence: this installed original
DIGI9652 has its main bracket only. JACK/ALSA 1–8 (ADAT1) were audibly
confirmed PASS, and 9–16 (ADAT2) were audibly confirmed PASS. The separate
ADAT3 expansion bracket is not installed, so 17–24 are supported by the card
and driver and are software-path tested only. Outputs 25–26 are S/PDIF and
were not part of the ADAT acceptance test. No document or report should treat
all 24 ADAT outputs as physically confirmed on this hardware.

The tones never start automatically. After a successful boot, use:

```text
sc-adat-tone-test start                 # 60 s, -36 dBFS/channel
sc-adat-tone-test start 120 -30
sc-adat-tone-test status
sc-adat-tone-test stop
sc-adat-tone-test scan                   # one second per output
sc-adat-report                           # complete boot evidence
```

Levels above -18 dBFS are rejected. Start and scan use 250 ms attack/release,
and the watchdog remains active if SSH disconnects. A test fails if JACK or
scsynth dies or if the JACK xrun delta is nonzero; it records evidence and
does not crash the appliance. Boot evidence is in
`/var/log/sc-adat-boot-report.log`; tone evidence is in
`/var/log/sc-adat-tone-test.log`.

This validates software routing, channel order, timing, and xruns. Only the
subsequent powered optical-receiver/listening check validates real optical
output at the ADAT devices.
