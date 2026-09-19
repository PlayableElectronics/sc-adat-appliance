# U17 first-application physical test failure

Dates: 2026-09-19 and 2026-09-20

The derived candidate from commit `de42ce8` was programmed into the original
Dallas `DS1230Y-100` using TL866A profile `DS1230Y(RW)`. The programmer
verified the write, and three post-write reads were byte-identical to the
candidate (`cb5a4306ce73bef3b6ec76b18b367606d1a954e99d6584350c6b7ef394c9ee19`).

After reinstalling the DS1230 in the powered-off console and powering the
console, the display showed:

```text
Checksum Failed...
```

The supplied failure photograph is preserved at
[`image-1789846178798.jpg`](../photo/image-1789846178798.jpg). It shows the
Dyaxis/MultiDesk boot display with `Checksum Failed...` and the following
reset instruction text.

After removal from the powered-off console, three new read-only reads were
taken with the exact `DS1230Y(RW)` profile. All were 32,768 bytes,
byte-identical, and had SHA-256
`cb5a4306ce73bef3b6ec76b18b367606d1a954e99d6584350c6b7ef394c9ee19`.
Every changed-offset comparison against the programmed candidate reported
zero differences. Raw reads remain under the ignored local directory
`.local/dyaxis/ds1230-preservation/`.

This result does not demonstrate application execution. It falsifies the
previous assumption that the candidate's `AA55` at `FDFC/FDFD` plus calculated
checksum at `FDFE/FDFF` was sufficient for startup. More specifically, the
instruction-accurate emulator predicts **Checksum Good** at `0x02FD` under its
linear XDATA mapping, while the console displayed **Checksum Failed** at
`0x0311`; the marker branch alone does not explain the physical result. The
analysis is in [`U17_CHECKSUM_FAILURE_EMULATION.md`](U17_CHECKSUM_FAILURE_EMULATION.md).
The subsequent three-read retention diagnosis is in
[`U17_DS1230_RETENTION_DIAGNOSIS.md`](U17_DS1230_RETENTION_DIAGNOSIS.md).

No further write, candidate construction, serial transmission, or hardware
modification is authorized until the remaining physical address/decode and
startup validation behavior are resolved.

## Second confirmed physical failure

The guarded candidate procedure was run again on 2026-09-20 with the exact
`DS1230Y(RW)` profile. The candidate write/read-back was verified byte-for-byte
with SHA-256
`cb5a4306ce73bef3b6ec76b18b367606d1a954e99d6584350c6b7ef394c9ee19`. After
reinstallation in the powered-off console, Dyaxis again displayed:

```text
Checksum Failed...
```

This is a second confirmed physical failure of the candidate startup
assumption. It is not evidence of a Dallas retention or programmer fault: the
candidate was verified after programming. No new guessed image is authorized.
The candidate is retained only as diagnostic evidence and must not be reused
for another write without a separately reviewed procedure. The operator must
restore the canonical original with the guarded command in
`../DS1230_PROGRAMMING_PROCEDURE.md`; restoration is intentionally not
automatic.
