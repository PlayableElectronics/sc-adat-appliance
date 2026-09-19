# U17 embedded-message cross-reference

Register constant propagation resolves the external CODE `FE06` calls that
pass `R2:R1` pointers into these strings. The generated
`generated/u17/u17-fe06-calls.tsv` and `u17-register-resolved-abi.tsv` are the
authoritative machine-readable records; the earlier “none found” result was a
tooling limitation.

| ROM address | Message | Valid FE06 reference(s) | Context |
|---:|---|---|---|
| `0x03C5`/pointer `03C6` | Beginning Manufacturing Diagnostics | `0244` | Startup diagnostics |
| `0x03EA` | Please Wait... | `0251` | Startup wait |
| `0x03F9` | Non-Volatile RAM Has Been Cleared... | `0266` | Clear path |
| `0x041E` | Booting... | `0273`, `02C3`, `0328` | Startup/validation branches |
| `0x0429` | Unconditional Launch... | `028D` | Launch path |
| `0x0441` | Updating Firmware to a New Version... | `02B6` | External-RAM transfer path |
| `0x0467` | Checksumming Battery-Backed RAM... | `02D7` | `037C` checksum path |
| `0x048A` | Checksum Good... | `02FD` | Validation success |
| `0x049B` | Launching... | `030A` | Launch path |
| `0x04A8` | Checksum Failed... | `031B` | Validation failure |
| `0x04BB` | MultiDesk Boot ROM, version 1.06, 28-Jun-94 | `0359` | Identification |
| `0x04E7` | Copyright (C) 1994 Studer-Editech Corporation | `0366` | Identification |
| `0x0515` | For Master Reset Press M1 and F1 at Power-On | `0373` | Reset instruction |
| `0x33CD`/pointer `33CE` | Launch... | `31AF` | Runtime launch/status path |

These are code-pointer references, not MOVC table guesses. The FE06 body is
outside U17, so display placement/style semantics beyond the observed register
values remain unresolved.
