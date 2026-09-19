# U17 external CODE dependencies

The reachable U17 image makes **67** literal external CODE call
references. The full caller/target table is `u17-external-code-dependencies.tsv`.

The repeated `0xFE00..0xFE6F` calls and `0xFEC1..0xFEF9` interrupt-service
targets are outside the 32 KiB EPROM. Static evidence cannot distinguish
mirrored ROM, FPGA/peripheral-provided bus behavior, external RAM overlays,
or another socketed ROM. The two undumped socketed ROM candidates remain
possible contributors, but no target-to-socket mapping is proven.

`LCALL 0x8000` is a distinct external-code launch after the U17 transfer and
validation path; it is not evidence that the external CODE service calls are
ordinary registers.
