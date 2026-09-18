# U17 embedded-message cross-reference

The table covers every meaningful printable U17 message. Addresses are ROM
addresses from the verified image. The control-flow-aware output contains no
valid direct `MOVC`/DPTR reference that names these string addresses; the
messages are therefore likely reached through indirect tables or external
service call `0xFE06`. This is an absence of direct references, not proof that
the messages are unused.

| ROM address | Message | Direct valid refs | Containing routine / calls before or after |
|---:|---|---|---|
| `0x03C5` | `Beginning Manufacturing Diagnostics` | none found | Startup `0x01E0` initializes services, then calls `0xFE06`; `0x0DFE` follows the first diagnostic display calls |
| `0x03EA` | `Please Wait...` | none found | Same indirect `0xFE06` display/message path |
| `0x03F9` | `Non-Volatile RAM Has Been Cleared...` | none found | Near `0x03A4`, which clears `0x8000–0xFDFD`; message dispatch is indirect |
| `0x041E` | `Booting...` | none found | Startup/launch path; indirect display service |
| `0x0429` | `Unconditional Launch...` | none found | Associated with `0x328A -> LCALL 0x8000` path; indirect dispatch |
| `0x0441` | `Updating Firmware to a New Version...` | none found | External-RAM/download state machine and `0xFE06` calls |
| `0x0467` | `Checksumming Battery-Backed RAM...` | none found | `0x037C` checksum routine and startup validation |
| `0x048A` | `Checksum Good...` | none found | Validation-success branch before local/external launch services |
| `0x049B` | `Launching...` | none found | Launch branch around `0x328A` |
| `0x04A8` | `Checksum Failed...` | none found | Validation-failure branch returning to diagnostic/service handling |
| `0x04BB` | `MultiDesk Boot ROM, version 1.06, 28-Jun-94` | none found | Identification text; likely indirect diagnostic display/host service |
| `0x04E7` | `Copyright (C) 1994 Studer-Editech Corporation` | none found | Identification text; likely indirect display/host service |
| `0x0515` | `For Master Reset Press M1 and F1 at Power-On` | none found | Firmware-evidenced diagnostic control for the observation worksheet |
| `0x33CD` | `Launch...` | none found | Containing routine unresolved; nearby `0x33D8` low-level service routine, but direct string use not recovered |

The nearest confirmed message-call mechanism is startup register setup followed
by repeated `LCALL 0xFE06`; the external target likely selects text and output
destination. Recovering the exact message index table requires tracing the FPGA/
external service bus or capture, not a raw string scan.
