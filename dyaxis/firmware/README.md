# Studer Dyaxis/MultiDesk firmware archive

This directory contains deliberately published historical firmware for
surviving Studer-Editech Dyaxis/MultiDesk hardware. The original image is
kept byte-for-byte; analysis outputs belong elsewhere and must never replace
or modify an original image.

## U17 V1.06

- Board/socket: Studer Dyaxis II controller board, socket `U17`; the first
  host-communication firmware target associated with the controller's rear
  `RS-422` ports.
- Processor: Philips `P80C552`, 8051 family.
- EPROM: AMD `AM27C256-95DC`, DIP-28, 32 KiB.
- Label: `41.005.415.Z1 / U17 V1.06 / SEC 1994`.
- Embedded identification: `MultiDesk Boot ROM, version 1.06, 28-Jun-94`.
- Published filename:
  `original/41.005.415.Z1-U17-V1.06-AM27C256.bin`.
- Size: 32,768 bytes.
- SHA-256:
  `22aa7788f49abf0c5ad31d0bc15fb2048cacaec1bac8cec0ddde87e29854e0dd`.

## Provenance and verification

The source device was read three independent times after confirming pin-1/notch
orientation against the programmer socket diagram. All three reads were
exactly 32,768 bytes, byte-for-byte identical, and produced the SHA-256 above.
The image was not erased, programmed, blank-checked, protected, unprotected,
or otherwise modified.

The programmer was a TL866A, reported by `minipro` as firmware `03.2.86`.
The macOS USB identity was MiniPro TL-866, VID `0x04d8`, PID `0xe11c`. The
tool was `minipro 0.7.4`, commit
`3808aecb6a1dac9906a9691b93820ee1bd2b7a18`, using the exact database
definition `AM27C256@DIP28` (`Memory: 32768 Bytes`, `Package: DIP28`). Each
read used the explicit read-only form:

```text
minipro -p 'AM27C256@DIP28' -r '<raw-output-path>.bin'
```

Verify the published copy from the repository root with either:

```sh
sha256sum dyaxis/firmware/original/41.005.415.Z1-U17-V1.06-AM27C256.bin
shasum -a 256 dyaxis/firmware/original/41.005.415.Z1-U17-V1.06-AM27C256.bin
```

Or verify the manifest from this directory with:

```sh
sha256sum -c SHA256SUMS
```

## Uptown Automation U7, MI V2.7++

- Board manufacturer: Uptown Automation Systems, Inc., Boulder, Colorado,
  USA.
- Board role: multichannel control/fader automation board associated with the
  Dyaxis/MultiDesk surface.
- Processor: Intel/Philips PCB 80C552-5.
- Processor crystal: 24.000 MHz.
- EPROM socket: `U7`; adjacent following IC reference: `U8`.
- EPROM: ST/SGS-Thomson `M27C128-12F1`, DIP-28, 16 KiB / 16,384 bytes.
- Sticker transcription (provisional; the sticker was not peeled further):
  `MI V2.7++ / 490-0270 / SUM 0F1C`.
- The printed `12.75V PGM` marking is programming information only; it was
  not used and the device was never programmed.
- Provenance photographs already stored in this repository include
  [`2694.jpg`](../photo/2694.jpg) (Uptown Automation fader-board context) and
  [`2695.jpg`](../photo/2695.jpg) (U7/U8-area component context).
- Published filename: `original/490-0270-MI-V2.7-M27C128.bin`.
- Size: 16,384 bytes.
- Read date: 2026-09-18.
- SHA-256:
  `a29a17def1f51a6475d21da22a93bd9adf2c7c62f984f87c15170c2bd78eb0c3`.

This image was read three independent times using the TL866A and the
read-compatible `AM27C128@DIP28` definition. The installed database reported
`Memory: 16384 Bytes` and `Package: DIP28`. Each read used only:

```text
minipro -p 'AM27C128@DIP28' -r '<raw-output-path>.bin'
```

All three reads were exactly 16,384 bytes, byte-for-byte identical, and
non-blank. The programmer reported chip ID `0x0116 OK` during each read. This
is a distinct Uptown Automation U7 controller/fader-board image, not the
Studer-Editech U17 MultiDesk Boot ROM above; the comparison and initial 8051
analysis are recorded in
[`../analysis/EPROM_490-0270-MI-V2.7-M27C128_INITIAL.md`](../analysis/EPROM_490-0270-MI-V2.7-M27C128_INITIAL.md).

## U3 Edit Panel V1.1

- Board: `DYAXIS II CONSOLE EDIT PANEL CPU BOARD`, assembly `41.005.430.01`.
- EPROM socket/reference: `U3`.
- EPROM: AMD `AM27C256-95DC`, DIP-28, 32 KiB / 32,768 bytes.
- Label transcription is approximate: `41.005.431.11 / U3 EDIT V1.1 / SEP
  1994`.
- Processor: Philips/Intel `P80C552`, 8051 family.
- Published filename:
  `original/41.005.431.11-U3-EDIT-V1.1-AM27C256.bin`.
- Size: 32,768 bytes.
- Read date: 2026-09-18.
- SHA-256:
  `7de44a1ed4ccadbafb3ef62e8f50383919c25bc32fbc6c7e74013dd4747f22b3`.

The installed database definition reported `Memory: 32768 Bytes` and
`Package: DIP28`. Three independent reads used only:

```text
minipro -p 'AM27C256@DIP28' -r '<raw-output-path>.bin'
```

All three files were exactly 32,768 bytes, byte-for-byte identical, and
non-blank. The UV window was briefly exposed during identification and was
subsequently covered with an opaque label; the EPROM was never erased,
programmed, blank-checked, or protection-modified.

This U3 image is Studer-Editech Console Edit Panel firmware, distinct from the
U17 MultiDesk Boot ROM and the Uptown Automation U7 controller/fader firmware.
The control-flow-aware first-pass disassembly and cross-ROM comparison are in
[`../analysis/EPROM_41.005.431.11-U3-EDIT-V1.1_INITIAL.md`](../analysis/EPROM_41.005.431.11-U3-EDIT-V1.1_INITIAL.md).

## Preservation notice

These firmware images are preserved for historical research, maintenance,
repair, interoperability and continued use of surviving Studer-Editech
Dyaxis/MultiDesk hardware. They are provided exactly as read from original
devices, with provenance and cryptographic checksums. This repository does not
claim authorship, ownership or relicensing rights over the original firmware.
No trademark affiliation or endorsement is implied. If you are an appropriate
rights holder and have a concern about this archival material, please open a
repository issue with sufficient information to evaluate the request.

The repository has no general license file at the time of this archive entry.
Any future general repository license applies to original repository
code/documentation only; it does not grant rights to these third-party
firmware images.

## Additional images

Use `original/<board-or-socket>-<label-or-version>-<part>.bin` for each future
image. Add only a deliberately verified image, one matching entry in
`SHA256SUMS`, and a provenance section here or in a linked record. Keep raw
intermediate reads and programmer temporary files under ignored `.local/`
paths. Derived disassembly, strings, and analysis reports must not contain
replacement or modified copies of an original image.
