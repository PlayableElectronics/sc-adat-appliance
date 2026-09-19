# U17 external CODE dependencies

The current reachable U17 image makes **67** literal external CODE
call references. Exact call-site addresses and targets are in
`u17-external-code-dependencies.tsv`; call-site register/memory context is in
`u17-fe-abi.tsv`; grouped target/family counts are in `u17-fe-abi-summary.tsv`.

FE-page groups are separated into ordinary FE-page service calls and
`0xFEC0..0xFEF9` interrupt/service shims. Context is evidence for inputs and
post-return observations; a single call is not promoted into a display,
serial, timer or storage API without repeated supporting sites.

These targets are outside the EPROM and may be mirrored ROM, peripheral/FPGA
bus behavior, external RAM overlays or another socketed ROM. `LCALL 0x8000`
remains a distinct external-code launch after transfer/validation.
