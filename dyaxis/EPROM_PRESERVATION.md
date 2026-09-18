# Dyaxis II EPROM preservation record

## Verified source

- Board/socket: Studer Dyaxis II controller board, socket `U17`; first
  host-communication firmware target connected to the rear RS-422 ports.
- EPROM: AMD `AM27C256-95DC`, DIP-28, 32 KiB / 32,768 bytes.
- Label: `41.005.415.Z1 / U17 V1.06 / SEC 1994`.
- Associated processor: Philips `P80C552`, 8051 family.
- Programmer: TL866A, reported by `minipro` as firmware `03.2.86`; macOS USB
  identity was MiniPro TL-866, VID `0x04d8`, PID `0xe11c`.
- Tool: `minipro 0.7.4`, commit `3808aecb6a1dac9906a9691b93820ee1bd2b7a18`.
- Selected database definition: `AM27C256@DIP28`; `minipro -d` reports
  `Memory: 32768 Bytes` and `Package: DIP28`.
- Exact read-only command, repeated three times with distinct output paths:

  ```text
  minipro -p 'AM27C256@DIP28' -r '<raw-output-path>.bin'
  ```

- Read date: 2026-09-18.
- Orientation: pin 1/notch orientation was confirmed against the programmer
  socket diagram before the first read.

## Verification

The three raw reads were each exactly 32,768 bytes. They compared byte-for-byte
identically and each had SHA-256:

```text
22aa7788f49abf0c5ad31d0bc15fb2048cacaec1bac8cec0ddde87e29854e0dd
```

The image is not entirely `0x00` or entirely `0xFF`. No erase, program/write,
blank-check, protection, or automatic programming operation was used.

Canonical local copy (read-only mode `0444`):

```text
.local/dyaxis/eprom-dumps/41.005.415.Z1-U17-V1.06/41.005.415.Z1-U17-V1.06-AM27C256.bin
```

The raw intermediate reads remain ignored locally. The owner has explicitly
authorized publication of the verified canonical image as a historical,
repair, maintenance and interoperability artifact at
`dyaxis/firmware/original/41.005.415.Z1-U17-V1.06-AM27C256.bin`. No
unverified intermediate read is published.

## U7 — Uptown Automation MI V2.7++

- Board: Uptown Automation Systems, Inc., Boulder, Colorado, USA; multichannel
  control/fader automation board associated with the Dyaxis/MultiDesk surface.
- Processor: Intel/Philips PCB 80C552-5 with a 24.000 MHz crystal.
- Socket: `U7`; adjacent following IC reference: `U8`.
- EPROM: ST/SGS-Thomson `M27C128-12F1`, DIP-28, 16 KiB / 16,384 bytes.
- Sticker: provisional transcription `MI V2.7++ / 490-0270 / SUM 0F1C`;
  sticker was not peeled further. `12.75V PGM` is programming information
  only.
- Read date: 2026-09-18.
- Programmer/tool: TL866A, `minipro 0.7.4`, firmware `03.2.86`; approved
  read-compatible definition `AM27C128@DIP28`.
- Three reads were exactly 16,384 bytes and byte-for-byte identical; each
  produced SHA-256
  `a29a17def1f51a6475d21da22a93bd9adf2c7c62f984f87c15170c2bd78eb0c3`.
- Canonical local copy (read-only mode `0444`):
  `.local/dyaxis/eprom-dumps/490-0270-MI-V2.7-M27C128/490-0270-MI-V2.7-M27C128.bin`.
- Public copy:
  `dyaxis/firmware/original/490-0270-MI-V2.7-M27C128.bin`.
- This is the Uptown Automation U7 controller/fader-board firmware, distinct
  from the Studer-Editech U17 MultiDesk Boot ROM.

## U3 — Studer-Editech Console Edit Panel firmware

- Board: `DYAXIS II CONSOLE EDIT PANEL CPU BOARD`, assembly `41.005.430.01`.
- EPROM board reference: `U3`.
- EPROM: AMD `AM27C256-95DC`, DIP-28, 32 KiB / 32,768 bytes.
- Label transcription: approximately `41.005.431.11 / U3 EDIT V1.1 / SEP
  1994`; punctuation and exact spacing are preserved as uncertain.
- Associated processor: Philips/Intel P80C552, 8051 family.
- UV-window handling: the UV window was briefly exposed during identification
  and was subsequently covered with an opaque label. No erase or programming
  operation was performed.
- Programmer/tool: TL866A, `minipro 0.7.4`, firmware `03.2.86`; exact
  definition `AM27C256@DIP28` (`Memory: 32768 Bytes`, `Package: DIP28`).
- Read-only command, repeated three times with distinct output paths:

  ```text
  minipro -p 'AM27C256@DIP28' -r '<raw-output-path>.bin'
  ```

- Read date: 2026-09-18.
- Three reads were exactly 32,768 bytes, byte-for-byte identical, non-blank,
  and each produced SHA-256
  `7de44a1ed4ccadbafb3ef62e8f50383919c25bc32fbc6c7e74013dd4747f22b3`.
- Canonical local copy, mode `0444`:
  `.local/dyaxis/eprom-dumps/41.005.430.01-U3-EDIT-V1.1/41.005.431.11-U3-EDIT-V1.1-AM27C256.bin`.
- Public copy:
  `dyaxis/firmware/original/41.005.431.11-U3-EDIT-V1.1-AM27C256.bin`.
- This is Edit Panel firmware on the same assembly family as U17, not the U17
  MultiDesk Boot ROM and not the Uptown Automation U7 fader-board firmware.
