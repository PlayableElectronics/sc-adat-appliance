# U17 protocol candidate table

This table is intentionally conservative. It records what the ROM supports as
evidence, not a guessed packet format.

| Item | Evidence | Status |
|---|---|---|
| Serial entry | P80C552 SIO0 vector `0x0023 -> 0x3416` | Confirmed |
| Serial service | ISR `MOVX` reads `0xFED0`, calls external `0xFED1`, then `RETI` | Confirmed |
| UART registers | No reachable `S0CON`/`S0BUF` access in this ROM pass | Confirmed absence |
| External register window | Repeated `MOVX` and calls to addresses outside the 32 KiB image | Strong inference |
| RX/TX queue | Candidate internal-RAM references are listed separately; no queue is proven | Unresolved |
| Start marker | No packet marker promoted from ROM bytes | Requires capture |
| Length field | No length field promoted | Requires capture |
| Escape rule | No escape rule promoted | Requires capture |
| Checksum/CRC | No checksum routine identified with enough boundary/context evidence | Requires capture |
| ACK/retry/timeout | No reliable protocol-level identification | Requires capture |

The first capture should repeat one button press many times in both directions,
then correlate the stable request/reply byte sequences. Only after that should
one LED or motor-fader command be tested.
