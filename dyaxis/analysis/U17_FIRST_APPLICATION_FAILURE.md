# U17 first-application physical test failure

Date: 2026-09-19

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
checksum at `FDFE/FDFF` was sufficient for startup. The instruction-accurate
analysis is in [`U17_CHECKSUM_FAILURE_EMULATION.md`](U17_CHECKSUM_FAILURE_EMULATION.md).
The subsequent three-read retention diagnosis is in
[`U17_DS1230_RETENTION_DIAGNOSIS.md`](U17_DS1230_RETENTION_DIAGNOSIS.md).

No further write, candidate construction, serial transmission, or hardware
modification is authorized until the address/decode and dual marker/checksum
contract are resolved.
