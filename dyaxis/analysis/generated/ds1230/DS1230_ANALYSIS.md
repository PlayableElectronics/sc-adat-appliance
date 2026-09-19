# DS1230 read-only analysis

Input: `41.005.415.Z1-U17-DS1230Y-100.bin`; size `32768` bytes; SHA-256
`2e58841c485f9f805c159cee5901de053ca7397c20e5c08941328b6028152ca4`.

## Content and code plausibility

- All `0xFF`: **False**; all `0x00`: **False**.
- Zero bytes: `32353`; `0xFF` bytes: `102`;
  distinct byte values: `123`.
- Offset `0000` bytes: `0000000000000000`; plausible 8051 reset entry:
  **False**.
- If mapped at CPU `8000`, `LCALL 8000` fetches file offset `0000`; this image
  does not present a normal 8051 reset-style application entry there.
- CPU `FE00–FEF9` corresponds to file offsets `7E00–7EF9`; all-FF there:
  **False**. The region contains
  `43` 8051 `LJMP` trampolines into U17 CODE:
- `0xFE00` (file `0x7E00`) → U17 CODE `0x2442`
- `0xFE03` (file `0x7E03`) → U17 CODE `0x06EB`
- `0xFE06` (file `0x7E06`) → U17 CODE `0x075D`
- `0xFE09` (file `0x7E09`) → U17 CODE `0x22E2`
- `0xFE0C` (file `0x7E0C`) → U17 CODE `0x1F51`
- `0xFE0F` (file `0x7E0F`) → U17 CODE `0x205B`
- `0xFE12` (file `0x7E12`) → U17 CODE `0x07B8`
- `0xFE15` (file `0x7E15`) → U17 CODE `0x0821`
- `0xFE18` (file `0x7E18`) → U17 CODE `0x090D`
- `0xFE1B` (file `0x7E1B`) → U17 CODE `0x09E3`
- `0xFE1E` (file `0x7E1E`) → U17 CODE `0x1A2A`
- `0xFE21` (file `0x7E21`) → U17 CODE `0x1423`
- `0xFE24` (file `0x7E24`) → U17 CODE `0x0C14`
- `0xFE27` (file `0x7E27`) → U17 CODE `0x1D7E`
- `0xFE2A` (file `0x7E2A`) → U17 CODE `0x1ADC`
- `0xFE2D` (file `0x7E2D`) → U17 CODE `0x162C`
- `0xFE30` (file `0x7E30`) → U17 CODE `0x1551`
- `0xFE33` (file `0x7E33`) → U17 CODE `0x2182`
- `0xFE36` (file `0x7E36`) → U17 CODE `0x0680`
- `0xFE39` (file `0x7E39`) → U17 CODE `0x0542`
- `0xFE3C` (file `0x7E3C`) → U17 CODE `0x05C6`
- `0xFE3F` (file `0x7E3F`) → U17 CODE `0x0B4D`
- `0xFE42` (file `0x7E42`) → U17 CODE `0x0BD9`
- `0xFE45` (file `0x7E45`) → U17 CODE `0x1469`
- `0xFE48` (file `0x7E48`) → U17 CODE `0x14B3`
- `0xFE4B` (file `0x7E4B`) → U17 CODE `0x0C4B`
- `0xFE4E` (file `0x7E4E`) → U17 CODE `0x0A55`
- `0xFE51` (file `0x7E51`) → U17 CODE `0x007C`
- `0xFE54` (file `0x7E54`) → U17 CODE `0x1671`
- `0xFE57` (file `0x7E57`) → U17 CODE `0x21E6`
- `0xFE5A` (file `0x7E5A`) → U17 CODE `0x1C7B`
- `0xFE5D` (file `0x7E5D`) → U17 CODE `0x23C5`
- `0xFE60` (file `0x7E60`) → U17 CODE `0x037C`
- `0xFE63` (file `0x7E63`) → U17 CODE `0x168A`
- `0xFE66` (file `0x7E66`) → U17 CODE `0x12D5`
- `0xFE69` (file `0x7E69`) → U17 CODE `0x137B`
- `0xFE6C` (file `0x7E6C`) → U17 CODE `0x12AB`
- `0xFE6F` (file `0x7E6F`) → U17 CODE `0x1278`
- `0xFE72` (file `0x7E72`) → U17 CODE `0x180E`
- `0xFE75` (file `0x7E75`) → U17 CODE `0x1869`
- `0xFE78` (file `0x7E78`) → U17 CODE `0x1909`
- `0xFE7B` (file `0x7E7B`) → U17 CODE `0x19E2`
- `0xFE7E` (file `0x7E7E`) → U17 CODE `0x0076`
- Printable runs (minimum four bytes):
- `—` `none`

## Non-zero storage inventory

These are byte-presence regions only; classification is deliberately
conservative and is not inferred from position alone.

| File range | Bytes | Classification | Confidence |
|---|---:|---|---|
| `0x7E00–0x7E51` | 82 | CODE trampoline table | high |
| `0x7E53–0x7E7E` | 44 | CODE trampoline table | high |
| `0x7E80–0x7E80` | 1 | persistent state/configuration candidate | low |
| `0x7EC0–0x7EC1` | 2 | persistent state/configuration candidate | low |
| `0x7EC4–0x7EC5` | 2 | persistent state/configuration candidate | low |
| `0x7EC8–0x7EC9` | 2 | persistent state/configuration candidate | low |
| `0x7ECC–0x7ECD` | 2 | persistent state/configuration candidate | low |
| `0x7ED0–0x7ED1` | 2 | persistent state/configuration candidate | low |
| `0x7ED4–0x7ED5` | 2 | persistent state/configuration candidate | low |
| `0x7ED8–0x7ED9` | 2 | persistent state/configuration candidate | low |
| `0x7EDC–0x7EDD` | 2 | persistent state/configuration candidate | low |
| `0x7EE0–0x7EE1` | 2 | persistent state/configuration candidate | low |
| `0x7EE4–0x7EE5` | 2 | persistent state/configuration candidate | low |
| `0x7EE8–0x7EE9` | 2 | persistent state/configuration candidate | low |
| `0x7EEC–0x7EF1` | 6 | persistent state/configuration candidate | low |
| `0x7EF4–0x7EF5` | 2 | persistent state/configuration candidate | low |
| `0x7EF8–0x7EF9` | 2 | persistent state/configuration candidate | low |
| `0x7F00–0x7FFF` | 256 | unexplained retained/residual data | low |

## U17 startup markers and checksum

U17 sums file offsets `0000–7DFC` (CPU `8000–FDFC` inclusive), complements
the 16-bit result, and compares it big-endian at file offsets `7DFE–7DFF`.
The calculated sum is `0x0000` and complement is
`0xFFFF`. Stored checksum: `0x0000`.

Startup marker bytes at file offsets `7DFC–7DFD`: `0000`;
expected `AA55`; match: **False**.
The second startup marker/checksum pair at file offsets `7DFE–7DFF` is
`0000`; startup expects `AA55`: **False**.
The checksum comparison also reads `7DFE–7DFF`: **False**.

Under the linear XDATA hypothesis, the original contents would enter
`0x02CD`, calculate the checksum, fail the stored-byte comparison, and reach
`0x0311` (`Checksum Failed`). This is a static prediction for the archived
original, not proof of the physical chip mapping or of when the bytes became
zero. The later `de42ce8` candidate retained its checksum and is predicted by
the same model to reach `0x02FD` (`Checksum Good`), contrary to the physical
console result; this discrepancy leaves the simple mapping hypothesis
unconfirmed.

## Mapping limits

The bytes are compatible with the proposed `8000` file-offset relationship,
but the dump alone does not prove CODE versus XDATA visibility, chip-select
decode, or whether FE-page CODE is supplied by this device. A bus trace or
additional live-board evidence remains required.
