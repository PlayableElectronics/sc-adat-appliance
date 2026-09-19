# U17 external application image contract

This document records a superseded hypothesis. The first hardware test
(`de42ce8`) was read back byte-for-byte but produced `Checksum Failed...`.
Do not use this format to create or program another image.

| CPU range | File offset | Meaning | Evidence |
|---|---:|---|---|
| `8000..FDFB` | `0000..7DFB` | application payload and zero-filled remainder | `31C1/321C` block writes and `037C` checksum loop |
| `FDFC..FDFD` | `7DFC..7DFD` | startup marker `AA 55` | startup validation at `02A3..02AC` |
| `FDFE..FDFF` | `7DFE..7DFF` | startup marker `AA 55`, then reused as complemented checksum bytes | startup validation at `0293..02A1`; checksum comparison at `02D7..0304` |
| `FE00..FFFF` | `7E00..7FFF` | protected persistent trampoline/service window | verified DS1230 read; physical CODE decode remains a hardware hypothesis |

The checksum loop itself is confirmed over CPU `8000..FDFC` inclusive,
equivalently the half-open file slice `[0x0000, 0x7DFD)`. The stored bytes are
read from `FDFE/FDFF` high then low. However, startup first requires those same
bytes to equal `AA55`; the dual-use contract is unresolved and the simple
builder model is not hardware-valid.

The transfer routine accepts 128-byte blocks with block indices below `FC`,
which permits writes through `FDFF`; this transport bound is wider than the
payload area because it includes signature and checksum metadata. U17 launches
only after validation with `LCALL 8000`, so the application is entered as a
subroutine and must return with `RET` under the observed path.

`dyaxis/analysis/u17_image.py` remains a dependency-free offline arithmetic
tool, but its prior candidate format must not be treated as a startup
validator. It never opens a serial device and never modifies the preserved
DS1230 dump. Any future write/download experiment must use a replacement
memory device or an adapter, not the original DS1230.

Examples:

```sh
python3 dyaxis/analysis/u17_image.py validate dyaxis/firmware/original/41.005.415.Z1-U17-DS1230Y-100.bin
python3 dyaxis/analysis/u17_image.py build payload.bin \
  dyaxis/firmware/original/41.005.415.Z1-U17-DS1230Y-100.bin candidate.bin
```

The preserved original DS1230 fails both startup marker checks. For the
`de42ce8` candidate, the emulator follows the marker mismatch into `0x02CD`,
calculates `FDD7`, and predicts the `0x02FD` **Checksum Good** path because
both stored checksum-byte comparisons pass. The console instead displayed
**Checksum Failed** at `0x0311`. This falsifies the assumed linear XDATA
mapping or another part of the physical decode; no replacement image should
be built from this document.
