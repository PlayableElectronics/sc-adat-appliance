# Controlled DS1230Y candidate test

This is an operator procedure only. It was prepared without writing the
connected programmer or the Dyaxis. The candidate is a derived diagnostic
image, not original firmware, and the previous physical result is not being
reinterpreted as successful application execution.

## Images and deliberate differences

| Image | Size | SHA-256 |
|---|---:|---|
| `dyaxis/firmware/original/41.005.415.Z1-U17-DS1230Y-100.bin` | 32768 | `2e58841c485f9f805c159cee5901de053ca7397c20e5c08941328b6028152ca4` |
| `dyaxis/firmware/candidates/41.005.415.Z1-U17-first-app-SJMP-8000.bin` | 32768 | `cb5a4306ce73bef3b6ec76b18b367606d1a954e99d6584350c6b7ef394c9ee19` |

The candidate differs from the original at exactly six offsets:

```text
0000: 00 -> 80       0001: 00 -> FE       (SJMP $ at application entry)
7DFC: 00 -> AA      7DFD: 00 -> 55       (marker)
7DFE: 00 -> FD      7DFF: 00 -> D7       (stored complemented checksum)
```

All bytes `0x0002..0x7DFB` and `0x7E00..0x7FFF` are unchanged. The checksum
input is file slice `image[:0x7DFD]`, including offset `0x7DFC` and excluding
`0x7DFD`; the stored big-endian result is `FDD7`.

The original is tracked, mode `0444`, and the helper verifies its size, mode
and SHA-256 before any write. It is never an output path. Local pre-write and
post-write reads go only below ignored `.local/dyaxis/`.

## Hardware precautions and orientation

- Device: Dallas `DS1230Y-100`, 32K x 8 battery-backed SRAM, DIP-28.
- Programmer: TL866A; exact definition: `DS1230Y(RW)`. Never select
  `DS1230Y(TEST)`, `DS1230W`, `DS1230AB`, or a similar device.
- Power the console fully off before removing or reinstalling the DS1230.
- Use ESD protection and handle the device by its package. Do not peel labels.
- In the TL866A, align the chip's pin-1/notch end with the programmer socket
  diagram. In the Dyaxis, reinstall it in socket U17 with the same pin-1/notch
  orientation shown by the board socket silkscreen and the pre-removal photo.
- Do not connect the programmer to the powered console. Do not transmit serial
  data or probe the rear ports during this test.

## Dry run

From the repository root, with the TL866A connected and the DS1230 seated:

```sh
./dyaxis/analysis/program_ds1230_candidate.sh --dry-run
```

This checks the tracked files, mode, hashes, `minipro` presence, connected
programmer, and the exact `DS1230Y(RW)` definition reporting DIP28 and 32768
bytes. It issues no chip read, write, erase, verify, blank-check, protection,
or ID operation.

Do not proceed unless the dry run identifies a TL866A and the exact profile.

## Explicit candidate programming

Only when the dry run succeeds and the operator has confirmed the chip
orientation, run this one destructive command:

```sh
./dyaxis/analysis/program_ds1230_candidate.sh --write --confirm-candidate
```

The helper performs three fresh read-only pre-write reads and requires each to
match the canonical original and each other. It then issues only the explicit
`minipro -p 'DS1230Y(RW)' -w ...` write, immediately reads a new local
timestamped file, and requires size, SHA-256 and byte-for-byte equality with
the candidate. It stops at the first failure.

## Observation and rollback

After reinstalling the device, power the console on and photograph the entire
startup sequence and any final screen. Capture specifically: boot text,
`Checksum Good...` or `Checksum Failed...`, `Booting...`, reset/error text,
whether faders/LEDs/displays initialize, and the final waiting state. This
test does not guarantee any particular screen because the physical memory
decode remains unresolved.

To restore the verified original, power the console fully off, remove the
DS1230, confirm orientation, and run:

```sh
./dyaxis/analysis/program_ds1230_candidate.sh --restore-original --confirm-original
```

The same three-read pre-write gate and immediate read-back verification apply.
The canonical original remains unchanged throughout.
