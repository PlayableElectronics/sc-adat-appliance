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

All raw bytes are ignored locally and are intentionally absent from Git.
