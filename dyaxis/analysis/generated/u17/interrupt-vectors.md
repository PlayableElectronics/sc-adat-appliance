# U17 P80C552 interrupt-vector report

Observed at valid vector instruction boundaries in the disasm51 output.

| Vector | Address | Observed target |
|---|---:|---|
| RESET | `0x0000` | `RESET_TARGET` |
| EXT0 | `0x0003` | `jump_3452` |
| TIMER0 | `0x000B` | `jump_3470` |
| EXT1 | `0x0013` | `jump_33F8` |
| TIMER1 | `0x001B` | `jump_348E` |
| SIO0_UART | `0x0023` | `SERIAL_ISR` |
| SIO1_I2C | `0x002B` | `inline sequence` |
| T2_CAPTURE0 | `0x0033` | `jump_34AC` |
| T2_CAPTURE1 | `0x003B` | `jump_34CA` |
| T2_CAPTURE2 | `0x0043` | `jump_34E8` |
| T2_CAPTURE3 | `0x004B` | `jump_3506` |
| ADC_COMPLETE | `0x0053` | `jump_3524` |
| T2_COMPARE0 | `0x005B` | `jump_3434` |
| T2_COMPARE1 | `0x0063` | `jump_3542` |
| T2_COMPARE2 | `0x006B` | `jump_3560` |
| T2_OVERFLOW | `0x0073` | `jump_357E` |
