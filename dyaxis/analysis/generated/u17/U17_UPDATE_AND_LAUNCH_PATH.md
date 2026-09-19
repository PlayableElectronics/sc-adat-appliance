# U17 update, validation and launch path

## Confirmed sequence

1. `2F7D` clears XDATA `0000..7FFF` (the endpoint is exclusive).
2. `2F8B` separately clears XDATA `FE00..FFFF`.
3. `03A4` clears `8000..FDFC` and then explicitly clears `FDFE/FDFF`.
4. `31C1` accepts block/index values `0x00..0xFB`, computes
   `0x8000 + index*0x80`, and stores the received byte stream through the
   pointer held in internal RAM `9E:9F`; `321C` performs the `MOVX` write.
5. `037C` sums bytes in half-open range `[8000,FDFD)`, i.e. through `FDFC`,
   with 16-bit carry and returns the bitwise-complement in `R6:R7`.
6. Startup checks `FDFE/FDFF == AA55`, then `FDFC/FDFD == AA55`; any marker
   mismatch enters `02CD`, which computes and compares the complemented sum
   against `FDFE/FDFF`. The bytes need not change between these reads.
7. The success path calls `328A`, which disables services and executes
   `LCALL 8000`; the launched code is expected to return through the observed
   call frame before U17's reset-target call.

The block bound implies a maximum block start of `FD80` and a final 128-byte
block ending at `FDFF`. This is a transfer bound, not proof that every byte is
valid application code. Exact writes are listed in `u17-update-writes.tsv`.

## Unresolved

The wire framing, header fields, completion marker, checksum byte order as
sent by the host, and physical DS1230 chip-select mapping require a passive
bus/serial observation or a reviewed non-destructive memory read. No active
update should be attempted.
