# U17 external CODE dependencies

The current reachable U17 image makes **77** literal external CODE
call references. Exact call-site addresses and targets are in
`u17-external-code-dependencies.tsv`; call-site register/memory context is in
`u17-fe-abi.tsv`; grouped target/family counts are in `u17-fe-abi-summary.tsv`.

FE-page groups are separated into ordinary FE-page service calls and
`0xFEC0..0xFEF9` interrupt/service shims. Context is evidence for inputs and
post-return observations; a single call is not promoted into a display,
serial, timer or storage API without repeated supporting sites.

`LCALL` targets in `0xFE00..0xFEF9` are external CODE: the P80C552 fetches
executable instructions there. They are not ordinary peripheral registers.
The preserved DS1230 read provides direct evidence for the FE service window:
its file offsets `7E00..7E7F` contain 43 three-byte `LJMP` trampolines, under
the proposed `8000` mapping, including `FE06 -> U17 CODE 075D`,
`FE33 -> U17 CODE 2182`, and `FE60 -> U17 CODE 037C`. This resolves the FE
window provider more strongly than the U17 image alone; the physical chip
select and CODE/XDATA visibility still require bus evidence. MOVX peripheral
accesses remain a separate address-space category.

`FE06` has 16 resolved calls with CODE pointers in `R2:R1`; see
`U17_FE06_DISPLAY_ABI.md`. `FE33` has 10 calls. Its first eight
repeated sites pass `R7` values R7=0x00, R7=0x01, R7=0x02, R7=0x03, R7=0x04, R7=0x05, R7=0x06, R7=0x07, with `A`, `R4` and `R5`
zero at those sites. This supports a repeated indexed initialization/service
family, but does not prove whether it initializes display, timing, serial or
another subsystem. `LCALL 0x8000` remains a distinct external-code launch.
