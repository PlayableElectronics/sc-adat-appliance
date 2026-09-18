# Focused U17/U7 local-control comparison

Scope is limited to local startup, diagnostics, hardware control and transport
leads. No original-host software search or unrelated functionality is included.

| Evidence | U17 | Uptown U7 |
|---|---|---|
| Role | Studer-Editech boot/diagnostic and external-service controller | Local control/fader board firmware |
| Strings | boot, checksum, NVRAM, firmware update, launch, master reset | TEST MODE, channel remap, watchdog, RAM test, control panel, run/sync/raw modes |
| UART | No direct reachable S0CON/S0BUF setup; ISR delegates to external `0xFED0/0xFED1` | Direct S0CON/S0BUF setup at `0x1CA9`, transmit at `0x21EA` |
| Motor/fader evidence | Direct PWM/ADC activity not recovered in reachable U17 code | PWM0/PWM1, ADCON, per-channel loops and feedback logic are present |
| I/O scan evidence | P4/P5 activity exists but no complete surface scan identified | P1 row select, P4 read/write, P3.5 strobe strongly support local scan/output |
| Shared printable strings | None | None |
| Shared protocol constants | No reliable common framing set established | No reliable common framing set established |

The absence of matching strings does not exclude a binary protocol. Current
best architecture is distributed: U7 performs local fader/I/O work, while U17,
FPGA/PAL and Z85230-family hardware provide boot, service, decode and board/
host communication functions.
