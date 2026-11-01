# AW2816 MIDI foundation (Phase 1)

This package is optional and independent of the `adat-live-processor` audio
crate. It contains the transport-independent MIDI parser, lossless archive
format, `aw2816ctl` inspection/backup CLI, capability schema, and a
validation-only combined-preset boundary. It is not linked into or called by
the live audio callback. No parser, filesystem operation, MIDI output, Thru,
Echo, or preset application runs in that callback.

The implemented device-specific facts below are referenced to Yamaha's
*AW2816 Owner's Manual*, English edition E1. Protocol evidence is listed per
capability in [`capabilities.json`](capabilities.json). The manual is not copied
into this repository.

| Family | Phase 1 interpretation |
|---|---|
| Program Change / scenes | Decode/encode Program Change; parse scene Bulk envelopes. Assignment-table payload stays opaque. |
| Assignable Control Change | Decode/encode CC; parse assignment-table envelope. Entries stay opaque. |
| Parameter Change | Validate `F0 43 1n/3n 3E 07 type ... F7`; recognize the seven manual-listed types; retain addresses/data uninterpreted. |
| Bulk Dump / Request | Validate `LM  8C36` envelopes, data-name/selector layouts, byte count, and documented 7-bit checksum on dumps. Unknown payload bytes remain opaque. |
| MIDI Remote | Parse the documented `R` memory/bank envelopes. Contents stay opaque. |
| MMC | Parse unambiguous manual-listed commands. The command is never transmitted by this tool. |
| MMC Reset | Unsupported conflict: table 3.4.1.1 says `0x0F`; section 4.13.1.8 says `0x0D` (Appendix pp. 403, 405–406). Either byte is preserved and displayed as ambiguous. |
| MTC / SPP | Parse MIDI Quarter Frame and Song Position Pointer messages. No timing output or synchronization is implemented. |
| Automix | Parse the `A` Bulk envelope; preserve its event data as opaque bytes. |
| MIDI Clock output / synchronization | Documented but not implemented; no clock generation or synchronization occurs. |

No SysEx parameter addresses are invented. When a documented envelope contains
fields whose meanings are not established for this foundation, the exact bytes
remain available in the `ParsedMessage` and archive.

## Commands

Run from this directory:

```sh
cargo run -- ports
cargo run -- monitor --input 0
cargo run -- monitor --input 'MIDI Interface In' --output capture.jsonl
cargo run -- decode capture.jsonl
cargo run -- decode captured.rawmidi
cargo run -- inspect capture.jsonl
cargo run -- diff earlier.jsonl later.jsonl
cargo run -- backup --input 'MIDI Interface In' --output ./aw2816-backup --channel 1
cargo run -- backup --input 'MIDI Interface In' --output ./aw2816-backup --output-port 'MIDI Interface Out' --channel 3
cargo run -- validate-preset examples/combined-preset.json
```

`ports` enumerates MIDI ports through `midir` only; it does not open CPAL or the
audio system. A port selector may be an input/output index or a unique exact
port name. `monitor` opens only the selected MIDI input. It never opens or
sends to MIDI output and always creates a lossless JSON Lines capture (when
`--output` is omitted it creates a timestamp-named capture in the current
directory). Existing output files are not overwritten.

`backup` is the only command that opens MIDI output. It sends only the
documented AW2816 Yamaha Universal Bulk Request messages listed in manual
Appendix sections 4.13.2.2/4/6/8/10/12/14/16/18/20/22. The receiver channel is
explicitly selectable (1–16); verify it against the AW2816 Rx CH setting.
`--output-port` selects a paired output when the input and output port names
differ. It never sends Parameter Change, Program Change, MMC, scene recall,
Bulk Dump/restore data, or any other write/control message. Each response is
archived as received. `raw-input.bin` is the exact received byte stream and
`raw-output.bin` contains the exact requests sent; `events.jsonl` records their
ordering and metadata. An existing backup file is never overwritten.

## Capture/archive format v1

Each JSONL event carries an `archive_version`, sequence number, monotonic
nanoseconds from capture start, direction, source and destination port labels,
the raw callback bytes as lowercase hex, parser results/issues, and parser
library version. Concatenating `raw_midi_bytes_hex` in sequence order recreates
the original input stream exactly. Backup separates input and output raw
streams; the JSONL sequence identifies their combined send/receive order. Parsed
message raw fields are for inspection; archive event raw bytes are authoritative
for reconstruction, including fragmented SysEx and realtime bytes interleaved
within SysEx.

Interpretation is explicitly tagged `documented`, `inferred`, `unknown`, or
`conflict`. Checksum results are true/false for documented checksummed Bulk
Dumps and null where no checksum applies. Hex payloads are never normalized or
discarded.

## Diff and inspection

`inspect` reports message type, byte length, channel/device fields where known,
checksum status, known fields, unknown bytes, and raw message bytes. `diff`
compares known PC/CC/Parameter/Bulk envelope fields semantically, then reports
exact half-open raw byte ranges for payload differences and all unknown
messages. Message ordering and output text are deterministic. It does not infer
meanings for opaque data.

## Combined preset boundary

[`combined-preset.schema.json`](combined-preset.schema.json) and the typed
Rust validation model separate:

- `authoritative`: the Rust signature-DSP preset reference and desired Yamaha
  scene state;
- `captured_yamaha`: an archive identity, source port, and optional digest;
- `generated_yamaha_artifact`: materialized artifact/scene identity and source
  preset identity;
- `hardware_confirmation`: pending/confirmed/rejected state.

The CLI validates this document only. It does not apply DSP state, generate a
scene, send MIDI, or recall a scene. The example uses synthetic placeholders
and explicitly says it is not a hardware capture.

## Synthetic fixtures and tests

All MIDI byte sequences in unit tests are synthetic fixtures constructed from
the cited layouts. None were captured from an AW2816. Tests cover fragmented
SysEx, multiple messages and running status, realtime bytes interleaved with
SysEx, truncation, wrong Yamaha IDs, checksum success/failure, unknown payload
preservation, both ambiguous Reset bytes, exact archive reconstruction,
deterministic diff fields, request-output restrictions, preset validation, and
malformed parser inputs. See `cargo test` in this directory.

## Later hardware procedure

1. Connect AW2816 MIDI OUT/THRU (set to OUT) to Dell MIDI IN.
2. Connect Dell MIDI OUT to AW2816 MIDI IN.
3. Record all AW2816 MIDI settings, including MIDI/HOST, OUT/THRU, Rx CH,
   Bulk RX, Parameter Change RX/TX/ECHO, CC RX/TX/ECHO, PC RX/TX/ECHO, MMC,
   MTC, and MIDI Clock, before changing anything.
4. Initially run `aw2816ctl monitor` on Dell MIDI IN with Dell MIDI OUT closed.
5. Disable or verify MIDI Echo/Thru so that no feedback loop can occur. The
   AW2816 OUT/THRU connector must be set to OUT, not THRU, for this test.
6. Capture one control operation at a time and compare bytes. Do not infer an
   address from a label or adjacent parameter.
7. Before any future write test, make and verify a complete Bulk Dump backup.
8. If timing is later needed, use the AW2816's dedicated MTC OUT path.

## Hardware checklist — not yet performed

- [ ] Confirm Dell USB-MIDI interface input/output port identity.
- [ ] Confirm AW2816 MIDI/HOST is set to MIDI and MIDI OUT/THRU is set to OUT.
- [ ] Record current AW2816 MIDI configuration and Echo/Thru state.
- [ ] Verify passive monitor receives AW2816-originated MIDI and sends nothing.
- [ ] Confirm monitor sees PC, CC, Parameter Change, MMC, MTC/SPP and bulk traffic as enabled.
- [ ] Capture a complete Bulk Dump backup and verify each documented checksum.
- [ ] Compare two captures after changing one control at a time.
- [ ] Confirm the MMC Reset conflict from Yamaha or controlled hardware observation.
- [ ] Verify dedicated MTC OUT independently if timing work is scheduled.
- [ ] Confirm no Echo/Thru loop under the final cable configuration.

All items remain unchecked because the AW2816 is not connected.
