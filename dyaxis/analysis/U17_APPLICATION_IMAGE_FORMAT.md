# U17 external application image contract

This is the strongest contract recoverable from U17 instruction paths and the
verified DS1230 contents. It is an offline format description; it is not a
host download protocol and it authorizes no transmission or memory write.

| CPU range | File offset | Meaning | Evidence |
|---|---:|---|---|
| `8000..FDFB` | `0000..7DFB` | application payload and zero-filled remainder | `31C1/321C` block writes and `037C` checksum loop |
| `FDFC..FDFD` | `7DFC..7DFD` | required signature `AA 55` | startup validation at `0293..02AC` |
| `FDFE..FDFF` | `7DFE..7DFF` | complemented 16-bit checksum, big-endian | `037C` result compared by startup |
| `FE00..FFFF` | `7E00..7FFF` | protected persistent trampoline/service window | verified DS1230 read; physical CODE decode remains a hardware hypothesis |

The checksum input is exactly CPU `8000..FDFC` inclusive, equivalently the
half-open file slice `[0x0000, 0x7DFD)`. The stored checksum is the bitwise
complement of the 16-bit sum, written high byte then low byte. The payload
area before the signature is therefore at most `0x7DFC` (32,252) bytes.

The transfer routine accepts 128-byte blocks with block indices below `FC`,
which permits writes through `FDFF`; this transport bound is wider than the
payload area because it includes signature and checksum metadata. U17 launches
only after validation with `LCALL 8000`, so the application is entered as a
subroutine and must return with `RET` under the observed path.

`dyaxis/analysis/u17_image.py` provides a dependency-free offline validator
and builder. The builder requires a template image and copies its protected
`7E00..7FFF` suffix unchanged. It never opens a serial device and never
modifies the preserved DS1230 dump. Any future write/download experiment must
use a replacement memory device or an adapter, not the original DS1230.

Examples:

```sh
python3 dyaxis/analysis/u17_image.py validate dyaxis/firmware/original/41.005.415.Z1-U17-DS1230Y-100.bin
python3 dyaxis/analysis/u17_image.py build payload.bin \
  dyaxis/firmware/original/41.005.415.Z1-U17-DS1230Y-100.bin candidate.bin
```

The preserved DS1230 currently fails validation: its application area,
signature and checksum bytes are zero-filled. That is consistent with the
console's `Checksum Failed` message and does not justify repairing or writing
the original device.
