# Dyaxis firmware and permanent-storage inventory

Inventory compiled from preserved dumps, repository notes and board photos.
Unknowns are intentionally left unknown.

| Board/reference | Visible device/marking | Type/volatility | Capacity | Function/status | Hash |
|---|---|---|---:|---|---|
| Dyaxis II Console Edit Panel CPU, `41.005.430.01`, U3 | AMD `AM27C256-95DC`; label approx. `41.005.431.11 / U3 EDIT V1.1 / SEP 1994` | UV EPROM, nonvolatile | 32 KiB | Edit Panel firmware; verified three reads and publicly archived | `7de44a…f22b3` |
| Dyaxis controller CPU, U17 | AMD `AM27C256-95DC`; `41.005.415.Z1 / U17 V1.06 / SEC 1994` | UV EPROM, nonvolatile | 32 KiB | MultiDesk Boot ROM; verified three reads and publicly archived | `22aa77…e0dd` |
| Uptown Automation controller/fader, assembly `935 Rev B`, U7 | ST/SGS-Thomson `M27C128-12F1`; `MI V2.7++ / 490-0270 / SUM 0F1C` | UV EPROM, nonvolatile | 16 KiB | Fader/control-board firmware; verified three reads and publicly archived | `a29a17…eb0c3` |
| FPGA-area socket, reference unreadable | Studer label beginning `41.005.415.71` | Socketed programmable ROM; exact device not readable | Unknown | Candidate firmware/configuration source; not dumped | — |
| FPGA-area socket, reference unreadable | Studer label beginning `41.005.416.70` | Socketed programmable ROM; exact device not readable | Unknown | Candidate firmware/configuration source; not dumped | — |
| Main-board FPGA | `XILINX XC3030TM-70 PC68C` | Volatile SRAM FPGA, not permanent storage | Configuration size not established | Runtime programmable logic; external configuration source unknown | — |
| Main-board small controller beside FPGA | Marking and PCB reference not legible in available photos | Device class unconfirmed; internal program-memory and protection status unknown | Unknown | New physical trace evidence says it communicates with the XC3030; do not remove or read until identified | — |
| FPGA-area PLD | `PALC22V10L-25PC`, `9353 000020` | Nonvolatile programmable logic/fuse-map device, not byte-addressed firmware | Device logic capacity, not ROM bytes | Likely decode/glue; exact PCB reference and contents not preserved | — |
| Main-board serial controller | Zilog `Z85230`-family, full suffix unclear | Volatile register state | — | Dual-channel serial peripheral; no firmware storage | — |
| RS-422/interface board, U4 | `AM26LS32PC` | Differential receiver, volatile logic | — | Receive-side line interface candidate; not storage | — |
| RS-422/interface board, U13 | `SN75174N` | Differential driver, volatile logic | — | Transmit-side line interface candidate; not storage | — |
| U17 external battery-backed RAM window | Physical RAM device/reference not visible in available evidence | Volatile RAM with battery retention; exact technology unknown | Unknown | U17 strings and checksum path refer to battery-backed RAM; no separate dump or chip identity | — |
| Nearby 8-pin device | Marking/reference not readable in available photos | Unidentified; storage/function not assigned | Unknown | Preserve as unknown; no removal or programmer operation justified | — |
| Photo `2674` socketed Xicor device | Approx. visible marking `22-00958-000 / CS?1455` | Identity/function unresolved; package appears larger than 8-pin | Unknown | Do not call firmware storage; needs a clearer marking/photo | — |
| Photo `2673` device | P80C31-family marking only partially legible | ROMless 8051-family MCU candidate; volatile execution state | External program storage unknown | Processor identity/function not final | — |

The two Studer-labelled FPGA-area ROMs and the unidentified devices must not be
read with an approximate EPROM/PAL definition. Exact markings, references,
orientation and device family must precede any preservation operation.
