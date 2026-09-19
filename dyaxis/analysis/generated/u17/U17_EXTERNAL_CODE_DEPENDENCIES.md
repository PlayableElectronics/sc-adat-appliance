# U17 external CODE dependencies

The current reachable U17 image makes **67** literal external CODE
call references. Exact call-site addresses and targets are in
`u17-external-code-dependencies.tsv`; call-site register/memory context is in
`u17-fe-abi.tsv`; grouped target/family counts are in `u17-fe-abi-summary.tsv`.

FE-page groups are separated into ordinary FE-page service calls and
`0xFEC0..0xFEF9` interrupt/service shims. Context is evidence for inputs and
post-return observations; a single call is not promoted into a display,
serial, timer or storage API without repeated supporting sites.

`LCALL` targets in `0xFE00..0xFEF9` are external CODE: the P80C552 fetches
executable instructions there. They are not ordinary peripheral registers.
Possible sources are mapped persistent memory such as the DS1230 window,
executable RAM, or FPGA/PAL-supplied bus behavior; MOVX peripheral accesses
remain a separate address-space category. The U17 image cannot identify the
physical provider by itself.

`FE06` has 16 resolved calls with CODE pointers in `R2:R1`; see
`U17_FE06_DISPLAY_ABI.md`. `FE33` has 10 calls. Its first eight
repeated sites pass `R7` values R7=0x00, R7=0x01, R7=0x02, R7=0x03, R7=0x04, R7=0x05, R7=0x06, R7=0x07, with `A`, `R4` and `R5`
zero at those sites. This supports a repeated indexed initialization/service
family, but does not prove whether it initializes display, timing, serial or
another subsystem. `LCALL 0x8000` remains a distinct external-code launch.
