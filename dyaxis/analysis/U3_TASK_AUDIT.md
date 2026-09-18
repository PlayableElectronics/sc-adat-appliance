# Original U3 task audit

Status at commit `5fe1ba8` plus this analysis pass:

| Requirement | Status | Evidence or gap |
|---|---|---|
| Exact U3 EPROM identification and provenance | Complete | `EPROM_PRESERVATION.md`, firmware README |
| Three read-only reads, hashes, archive and metadata | Complete | Public binary, `SHA256SUMS`, preservation record |
| Basic P80C552 disassembly and clean-clone reproduction | Complete | `generated/u3/u3.reachable.asm`, prior clean-clone test |
| Display initialization/write path | Partial | Output-multiplex routine identified at `0x02A5`; display semantics and physical destination unresolved |
| Button/switch scanning | Complete at MCU-I/O level | Timer-0 path `0x0262 → 0x02D0` scans P5 through P4-selected rows |
| Wheel/encoder decoding | Unresolved | No explicit quadrature decoder proven; raw scan changes are queued |
| LED/output control | Partial | P4/P3 strobes and output buffers `0x30–0x3F` proven; LED assignment unresolved |
| Timer and watchdog logic | Partial | Timer 0 cadence and PWM timeout proven; no separate watchdog SFR access proven |
| Serial buffers/state machines | Complete at U3 level | RX `0x90–0x9F`, TX/event `0x80–0x8F`, pointers/counts `0x5D–0x62` |
| `0xFD`/`0xFE` protocol roles | Partial | Reset and immediate-send behavior proven; wire meaning unresolved |
| Length/address/command/checksum fields | Unresolved | No supported packet-field or checksum routine in U3 reachable code |
| U17/U3/U7 responsibility map | Complete as evidence-separated model | `THREE_CONTROLLER_ARCHITECTURE.md` |
| Permanent-storage inventory | Complete with undumped/unknown entries marked | `FIRMWARE_STORAGE_INVENTORY.md` |
| RS-422 ownership and wire baud | Unresolved | Requires transceiver/pinout evidence and passive capture |

No replacement firmware or transmit-capable host tooling is justified by this
pass.
