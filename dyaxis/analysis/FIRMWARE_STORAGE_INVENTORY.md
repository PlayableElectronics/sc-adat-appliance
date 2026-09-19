# Dyaxis firmware and permanent-storage inventory

Inventory compiled from preserved dumps, repository notes and board photos.
Unknowns are intentionally left unknown.

| Board/reference | Visible device/marking | Type/volatility | Capacity | Function/status | Hash |
|---|---|---|---:|---|---|
| Dyaxis II Console Edit Panel CPU, `41.005.430.01`, U3 | AMD `AM27C256-95DC`; label approx. `41.005.431.11 / U3 EDIT V1.1 / SEP 1994` | UV EPROM, nonvolatile | 32 KiB | Edit Panel firmware; verified three reads and publicly archived | `7de44a…f22b3` |
| Dyaxis controller CPU, U17 | AMD `AM27C256-95DC`; `41.005.415.Z1 / U17 V1.06 / SEC 1994` | UV EPROM, nonvolatile | 32 KiB | MultiDesk Boot ROM; verified three reads and publicly archived | `22aa77…e0dd` |
| Uptown Automation controller/fader, assembly `935 Rev B`, U7 | ST/SGS-Thomson `M27C128-12F1`; `MI V2.7++ / 490-0270 / SUM 0F1C` | UV EPROM, nonvolatile | 16 KiB | Fader/control-board firmware; verified three reads and publicly archived | `a29a17…eb0c3` |
| FPGA-area socket, reference unreadable | Studer label beginning `41.005.415.71` | Socketed programmable ROM; exact device not readable | Unknown | Possible firmware/configuration source; not dumped; not a serial-interface device | — |
| FPGA-area socket, reference unreadable | Studer label beginning `41.005.416.70` | Socketed programmable ROM; exact device not readable | Unknown | Possible firmware/configuration source; not dumped; not a serial-interface device | — |
| Main controller, U18 | Toshiba `TC55257BSPL-10` | Volatile SRAM | 32 KiB | Strong candidate for cleared working/XDATA RAM at `0000..7FFF`; no dump retained | — |
| Main controller, battery-backed RAM | Dallas `DS1230Y-100` | Nonvolatile battery-backed SRAM | 32 KiB | Three identical read-only dumps; populated image preserved publicly as a byte-exact archival read; physical decode remains partly unresolved | `2e5884…28152ca4` |
| Main-board FPGA | `XILINX XC3030TM-70 PC68C` | Volatile SRAM FPGA, not permanent storage | Configuration size not established | Runtime programmable logic; external configuration source unknown | — |
| FPGA-area PLD beside XC3030 | `PALC22V10L-25PC`, `9353 000020` | Nonvolatile programmable logic device; not executable CPU firmware | Logic configuration, not ROM bytes | Probable address-decoding/control/timing/glue logic around XC3030; exact equations and stateful role unknown | — |
| Main-board serial controller | Zilog `Z85230`-family, full suffix unclear | Volatile register state | — | Dual-channel serial peripheral; no firmware storage | — |
| RS-422/interface board, U4 | `AM26LS32PC` | Differential receiver, volatile logic | — | Receive-side line interface candidate; not storage | — |
| RS-422/interface board, U13 | Supplied identification `SN75177AN`; close-up `image-1789838660551.jpg` visibly appears to read `SN75174AN` | Differential-interface logic, volatile | — | Line-interface device, not ROM or firmware storage; marking discrepancy requires later resolution | — |
| Nearby 8-pin device | Marking/reference not readable in available photos | Unidentified; storage/function not assigned | Unknown | Preserve as unknown; no removal or programmer operation justified | — |
| Photo `2674` socketed Xicor device | Approx. visible marking `22-00958-000 / CS?1455` | Identity/function unresolved; package appears larger than 8-pin | Unknown | Do not call firmware storage; needs a clearer marking/photo | — |
| Photo `2673` device | P80C31-family marking only partially legible | ROMless 8051-family MCU candidate; volatile execution state | External program storage unknown | Processor identity/function not final | — |

The two FPGA-area socketed devices remain unidentified storage/configuration
candidates and must not be read with an approximate EPROM/PAL definition.
U13/U14 are differential-interface devices, not undumped ROMs. The DS1230 is
the preservation priority: do not remove or write it; establish a reviewed
read-only in-system method first.
