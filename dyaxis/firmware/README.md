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
