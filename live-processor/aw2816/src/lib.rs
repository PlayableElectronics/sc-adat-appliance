#![forbid(unsafe_code)]

use serde::{Deserialize, Serialize};
use std::time::Instant;

pub const LIBRARY_VERSION: &str = env!("CARGO_PKG_VERSION");
pub const MAX_SYSEX_BYTES: usize = 64 * 1024;
const YAMAHA: u8 = 0x43;
const DIGITAL_MIXER_GROUP: u8 = 0x3e;
const AW2816_MODEL: u8 = 0x07;
const BULK_FORMAT: u8 = 0x7e;
const BULK_MAGIC: [u8; 8] = *b"LM  8C36";

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(tag = "type", rename_all = "snake_case")]
pub enum MessageKind {
    NoteOff {
        channel: u8,
        note: u8,
        velocity: u8,
    },
    NoteOn {
        channel: u8,
        note: u8,
        velocity: u8,
    },
    PolyPressure {
        channel: u8,
        note: u8,
        pressure: u8,
    },
    ControlChange {
        channel: u8,
        controller: u8,
        value: u8,
    },
    ProgramChange {
        channel: u8,
        program: u8,
    },
    ChannelPressure {
        channel: u8,
        pressure: u8,
    },
    PitchBend {
        channel: u8,
        value: u16,
    },
    MtcQuarterFrame {
        value: u8,
    },
    SongPositionPointer {
        position: u16,
    },
    SystemCommon {
        status: u8,
        data: Vec<u8>,
    },
    Realtime {
        status: u8,
    },
    YamahaParameterChange {
        midi_channel: u8,
        mode: u8,
        parameter_type: u8,
        family: Option<ParameterFamily>,
        raw_data: Vec<u8>,
    },
    YamahaBulkDump {
        midi_channel: u8,
        data_name: u8,
        selectors: Vec<u8>,
        raw_payload: Vec<u8>,
        checksum: u8,
        checksum_valid: bool,
    },
    YamahaBulkRequest {
        midi_channel: u8,
        data_name: u8,
        selectors: Vec<u8>,
    },
    YamahaBulkUnknown {
        midi_channel: u8,
        direction: String,
        data_name: u8,
        opaque_tail: Vec<u8>,
        checksum: Option<u8>,
        checksum_valid: Option<bool>,
    },
    Mmc {
        device_id: u8,
        command: u8,
        command_name: String,
        raw_payload: Vec<u8>,
    },
    AmbiguousMmcCommand {
        device_id: u8,
        command: u8,
        reason: String,
        raw_payload: Vec<u8>,
    },
    UnknownSysEx {
        reason: String,
    },
    Unknown {
        status: Option<u8>,
        reason: String,
    },
    Malformed {
        reason: String,
    },
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum ParameterFamily {
    EditBufferByte,
    SetupMemoryByte,
    FunctionCall,
    EditBuffer7Bit,
    EditBufferBit,
    SetupMemoryBit,
    KeyRemoteBit,
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Interpretation {
    Documented,
    Inferred,
    Unknown,
    Conflict,
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ParsedMessage {
    /// Bytes exactly as observed for this parser event; running-status messages
    /// can omit their repeated status byte. Archive reconstruction uses chunks.
    pub raw_midi_bytes: Vec<u8>,
    pub kind: MessageKind,
    pub interpretation: Interpretation,
    pub checksum_passed: Option<bool>,
}

impl ParsedMessage {
    pub fn serialize_exact(&self) -> Vec<u8> {
        self.raw_midi_bytes.clone()
    }
}

#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ParseIssue {
    pub raw_midi_bytes: Vec<u8>,
    pub reason: String,
}

#[derive(Clone, Debug, Default, Serialize, Deserialize, PartialEq, Eq)]
pub struct ParseBatch {
    pub messages: Vec<ParsedMessage>,
    pub issues: Vec<ParseIssue>,
}

#[derive(Clone, Debug)]
struct Pending {
    status: u8,
    expected: usize,
    data: Vec<u8>,
    raw: Vec<u8>,
}

/// Bounded incremental MIDI parser. Realtime bytes can occur between arbitrary
/// SysEx fragments. A SysEx is capped at 64 KiB; truncation is emitted by finish.
#[derive(Default)]
pub struct StreamParser {
    running_status: Option<u8>,
    pending: Option<Pending>,
    sysex: Option<Vec<u8>>,
}

impl StreamParser {
    pub fn new() -> Self {
        Self::default()
    }

    pub fn push(&mut self, bytes: &[u8]) -> ParseBatch {
        let mut out = ParseBatch::default();
        for &byte in bytes {
            if byte >= 0xf8 {
                let documented = matches!(byte, 0xf8 | 0xfa | 0xfb | 0xfc | 0xfe | 0xff);
                out.messages.push(message(
                    vec![byte],
                    MessageKind::Realtime { status: byte },
                    if documented {
                        Interpretation::Documented
                    } else {
                        Interpretation::Unknown
                    },
                    None,
                ));
                continue;
            }
            if let Some(sx) = self.sysex.as_mut() {
                if byte == 0xf7 {
                    sx.push(byte);
                    let raw = self.sysex.take().unwrap_or_default();
                    out.messages.push(parse_complete(raw));
                    continue;
                }
                if byte & 0x80 == 0 {
                    sx.push(byte);
                    if sx.len() > MAX_SYSEX_BYTES {
                        let raw = self.sysex.take().unwrap_or_default();
                        out.issues.push(ParseIssue {
                            raw_midi_bytes: raw,
                            reason: format!("SysEx exceeds {} byte limit", MAX_SYSEX_BYTES),
                        });
                    }
                    continue;
                }
                let raw = self.sysex.take().unwrap_or_default();
                out.issues.push(ParseIssue {
                    raw_midi_bytes: raw,
                    reason: "SysEx interrupted by non-realtime status before EOX".into(),
                });
            }
            if byte == 0xf0 {
                self.flush_pending(&mut out, "status interrupted incomplete MIDI message");
                self.running_status = None;
                self.sysex = Some(vec![byte]);
                continue;
            }
            if byte & 0x80 != 0 {
                self.flush_pending(&mut out, "new status interrupted incomplete MIDI message");
                if byte < 0xf0 {
                    self.running_status = Some(byte);
                    self.pending = Some(Pending {
                        status: byte,
                        expected: channel_data_len(byte),
                        data: Vec::with_capacity(2),
                        raw: vec![byte],
                    });
                } else {
                    self.running_status = None;
                    let n = system_common_len(byte);
                    if n == 0 {
                        out.messages.push(parse_complete(vec![byte]));
                    } else {
                        self.pending = Some(Pending {
                            status: byte,
                            expected: n,
                            data: Vec::with_capacity(n),
                            raw: vec![byte],
                        });
                    }
                }
                continue;
            }
            if let Some(p) = self.pending.as_mut() {
                p.data.push(byte);
                p.raw.push(byte);
                if p.data.len() == p.expected {
                    let p = self.pending.take().unwrap_or(Pending {
                        status: 0,
                        expected: 0,
                        data: vec![],
                        raw: vec![],
                    });
                    out.messages
                        .push(parse_channel_or_common(p.status, p.data, p.raw));
                }
                continue;
            }
            if let Some(status) = self.running_status {
                let p = Pending {
                    status,
                    expected: channel_data_len(status),
                    data: vec![byte],
                    raw: vec![byte],
                };
                if p.data.len() == p.expected {
                    out.messages
                        .push(parse_channel_or_common(p.status, p.data, p.raw));
                } else {
                    self.pending = Some(p);
                }
                continue;
            }
            out.issues.push(ParseIssue {
                raw_midi_bytes: vec![byte],
                reason: "data byte without running status".into(),
            });
        }
        out
    }

    pub fn finish(&mut self) -> ParseBatch {
        let mut out = ParseBatch::default();
        self.flush_pending(&mut out, "truncated MIDI message at end of stream");
        if let Some(raw) = self.sysex.take() {
            out.issues.push(ParseIssue {
                raw_midi_bytes: raw,
                reason: "truncated SysEx: missing F7".into(),
            });
        }
        self.running_status = None;
        out
    }

    fn flush_pending(&mut self, out: &mut ParseBatch, reason: &str) {
        if let Some(p) = self.pending.take() {
            out.issues.push(ParseIssue {
                raw_midi_bytes: p.raw,
                reason: reason.into(),
            });
        }
    }
}

fn channel_data_len(status: u8) -> usize {
    match status & 0xf0 {
        0xc0 | 0xd0 => 1,
        _ => 2,
    }
}
fn system_common_len(status: u8) -> usize {
    match status {
        0xf1 => 1,
        0xf2 => 2,
        0xf3 => 1,
        0xf6 => 0,
        _ => 0,
    }
}
fn message(
    raw: Vec<u8>,
    kind: MessageKind,
    interpretation: Interpretation,
    checksum_passed: Option<bool>,
) -> ParsedMessage {
    ParsedMessage {
        raw_midi_bytes: raw,
        kind,
        interpretation,
        checksum_passed,
    }
}

fn parse_channel_or_common(status: u8, data: Vec<u8>, raw: Vec<u8>) -> ParsedMessage {
    let ch = status & 0x0f;
    let kind = match status {
        0x80..=0x8f => MessageKind::NoteOff {
            channel: ch,
            note: data[0],
            velocity: data[1],
        },
        0x90..=0x9f => MessageKind::NoteOn {
            channel: ch,
            note: data[0],
            velocity: data[1],
        },
        0xa0..=0xaf => MessageKind::PolyPressure {
            channel: ch,
            note: data[0],
            pressure: data[1],
        },
        0xb0..=0xbf => MessageKind::ControlChange {
            channel: ch,
            controller: data[0],
            value: data[1],
        },
        0xc0..=0xcf => MessageKind::ProgramChange {
            channel: ch,
            program: data[0],
        },
        0xd0..=0xdf => MessageKind::ChannelPressure {
            channel: ch,
            pressure: data[0],
        },
        0xe0..=0xef => MessageKind::PitchBend {
            channel: ch,
            value: data[0] as u16 | ((data[1] as u16) << 7),
        },
        0xf1 => MessageKind::MtcQuarterFrame { value: data[0] },
        0xf2 => MessageKind::SongPositionPointer {
            position: data[0] as u16 | ((data[1] as u16) << 7),
        },
        _ => MessageKind::SystemCommon { status, data },
    };
    let documented = matches!(
        kind,
        MessageKind::NoteOff { .. }
            | MessageKind::NoteOn { .. }
            | MessageKind::ControlChange { .. }
            | MessageKind::ProgramChange { .. }
            | MessageKind::MtcQuarterFrame { .. }
            | MessageKind::SongPositionPointer { .. }
    );
    let inferred = matches!(
        kind,
        MessageKind::PolyPressure { .. }
            | MessageKind::ChannelPressure { .. }
            | MessageKind::PitchBend { .. }
            | MessageKind::SystemCommon { .. }
    );
    message(
        raw,
        kind,
        if documented {
            Interpretation::Documented
        } else if inferred {
            Interpretation::Inferred
        } else {
            Interpretation::Unknown
        },
        None,
    )
}

fn parse_complete(raw: Vec<u8>) -> ParsedMessage {
    if raw.first() == Some(&0xf0) {
        return parse_sysex(raw);
    }
    let status = *raw.first().unwrap_or(&0xff);
    if status < 0xf0 {
        let d = if raw.first().is_some_and(|b| b & 0x80 != 0) {
            &raw[1..]
        } else {
            &raw[..]
        };
        return parse_channel_or_common(status, d.to_vec(), raw);
    }
    if status == 0xf1 || status == 0xf2 || status == 0xf3 {
        return parse_channel_or_common(status, raw[1..].to_vec(), raw);
    }
    if status == 0xf6 {
        return message(
            raw,
            MessageKind::SystemCommon {
                status,
                data: vec![],
            },
            Interpretation::Unknown,
            None,
        );
    }
    message(
        raw,
        MessageKind::Unknown {
            status: Some(status),
            reason: "undefined or unsupported system status".into(),
        },
        Interpretation::Unknown,
        None,
    )
}

fn parse_sysex(raw: Vec<u8>) -> ParsedMessage {
    if raw.len() < 2 || raw.last() != Some(&0xf7) {
        return message(
            raw,
            MessageKind::Malformed {
                reason: "SysEx missing framing byte".into(),
            },
            Interpretation::Unknown,
            None,
        );
    }
    if raw.starts_with(&[0xf0, 0x7f]) {
        return parse_mmc(raw);
    }
    if raw.get(1) != Some(&YAMAHA) {
        return message(
            raw,
            MessageKind::UnknownSysEx {
                reason: "not Yamaha manufacturer 0x43".into(),
            },
            Interpretation::Unknown,
            None,
        );
    }
    if raw
        .get(2)
        .is_some_and(|b| b & 0xf0 == 0x10 || b & 0xf0 == 0x30)
    {
        return parse_parameter(raw);
    }
    if raw
        .get(2)
        .is_some_and(|b| b & 0xf0 == 0x00 || b & 0xf0 == 0x20)
    {
        return parse_bulk(raw);
    }
    message(
        raw,
        MessageKind::UnknownSysEx {
            reason: "unrecognized Yamaha SysEx family".into(),
        },
        Interpretation::Unknown,
        None,
    )
}

fn parse_parameter(raw: Vec<u8>) -> ParsedMessage {
    if raw.len() < 7
        || raw.get(3) != Some(&DIGITAL_MIXER_GROUP)
        || raw.get(4) != Some(&AW2816_MODEL)
    {
        return message(
            raw,
            MessageKind::UnknownSysEx {
                reason: "Yamaha Parameter Change has wrong/truncated group or AW2816 model ID"
                    .into(),
            },
            Interpretation::Unknown,
            None,
        );
    }
    if raw[5..raw.len() - 1].iter().any(|b| *b >= 0x80) {
        return message(
            raw,
            MessageKind::Malformed {
                reason: "Parameter Change contains a non-7-bit data byte".into(),
            },
            Interpretation::Unknown,
            None,
        );
    }
    let sub = raw[2];
    let mode = (sub >> 4) & 0x07;
    let channel = sub & 0x0f;
    let t = raw[5];
    let family = match t {
        0x00 => Some(ParameterFamily::EditBufferByte),
        0x01 => Some(ParameterFamily::SetupMemoryByte),
        0x02 => Some(ParameterFamily::FunctionCall),
        0x10 => Some(ParameterFamily::EditBuffer7Bit),
        0x40 => Some(ParameterFamily::EditBufferBit),
        0x41 => Some(ParameterFamily::SetupMemoryBit),
        0x43 => Some(ParameterFamily::KeyRemoteBit),
        _ => None,
    };
    if family.is_none() {
        return message(
            raw.clone(),
            MessageKind::YamahaParameterChange {
                midi_channel: channel,
                mode,
                parameter_type: t,
                family,
                raw_data: raw[6..raw.len() - 1].to_vec(),
            },
            Interpretation::Unknown,
            None,
        );
    }
    message(
        raw.clone(),
        MessageKind::YamahaParameterChange {
            midi_channel: channel,
            mode,
            parameter_type: t,
            family,
            raw_data: raw[6..raw.len() - 1].to_vec(),
        },
        Interpretation::Documented,
        None,
    )
}

fn request_selector_count(name: u8) -> Option<usize> {
    match name {
        b'M' | b'R' | b'Q' | b'Y' | b'E' | b'T' | b'H' | b'A' => Some(1),
        b'S' | b'P' | b'C' => Some(0),
        _ => None,
    }
}
fn selector_valid(name: u8, selector: u8, request: bool) -> bool {
    match name {
        b'M' => selector <= (if request { 97 } else { 96 }) || selector == 127,
        b'R' => selector <= 3,
        b'Q' | b'Y' | b'E' => selector <= 127,
        b'T' => selector <= 20,
        b'H' => selector <= 64,
        b'A' => selector <= 16,
        _ => false,
    }
}
fn parse_bulk(raw: Vec<u8>) -> ParsedMessage {
    let sub = *raw.get(2).unwrap_or(&0);
    if raw.get(3) != Some(&BULK_FORMAT) {
        return message(
            raw,
            MessageKind::UnknownSysEx {
                reason: "Yamaha digital mixer group/model envelope is not AW2816 Bulk format 0x7E"
                    .into(),
            },
            Interpretation::Unknown,
            None,
        );
    }
    let is_request = sub & 0xf0 == 0x20;
    let midi_channel = sub & 0x0f;
    if is_request {
        if raw.get(4..12) != Some(BULK_MAGIC.as_slice()) || raw.len() < 14 {
            return message(
                raw,
                MessageKind::UnknownSysEx {
                    reason: "truncated/wrong Yamaha AW2816 Bulk Request signature".into(),
                },
                Interpretation::Unknown,
                None,
            );
        }
        let name = raw[12];
        let tail = &raw[13..raw.len() - 1];
        let Some(selector_count) = request_selector_count(name) else {
            return message(
                raw.clone(),
                MessageKind::YamahaBulkUnknown {
                    midi_channel,
                    direction: "request".into(),
                    data_name: name,
                    opaque_tail: tail.to_vec(),
                    checksum: None,
                    checksum_valid: None,
                },
                Interpretation::Unknown,
                None,
            );
        };
        if tail.len() != selector_count
            || tail.iter().any(|b| *b >= 0x80)
            || tail.iter().any(|s| !selector_valid(name, *s, true))
        {
            return message(raw,MessageKind::Malformed{reason:"Bulk Request selector length/range/encoding does not match documented data name".into()},Interpretation::Unknown,None);
        }
        return message(
            raw.clone(),
            MessageKind::YamahaBulkRequest {
                midi_channel,
                data_name: name,
                selectors: tail.to_vec(),
            },
            Interpretation::Documented,
            None,
        );
    }
    if raw.get(6..14) != Some(BULK_MAGIC.as_slice()) {
        return message(
            raw,
            MessageKind::UnknownSysEx {
                reason: "wrong or truncated Yamaha AW2816 Bulk Dump signature".into(),
            },
            Interpretation::Unknown,
            None,
        );
    }
    if raw.len() < 18 {
        return message(
            raw,
            MessageKind::Malformed {
                reason: "truncated Bulk Dump header".into(),
            },
            Interpretation::Unknown,
            None,
        );
    }
    let declared = ((raw[4] as usize) << 7) | (raw[5] as usize);
    let actual = raw.len().saturating_sub(7);
    if declared != actual {
        return message(
            raw,
            MessageKind::Malformed {
                reason: format!("Bulk byte count {declared} does not match framed count {actual}"),
            },
            Interpretation::Unknown,
            None,
        );
    }
    if raw[6..raw.len() - 1].iter().any(|b| *b >= 0x80) {
        return message(
            raw,
            MessageKind::Malformed {
                reason: "Bulk Dump contains a non-7-bit byte".into(),
            },
            Interpretation::Unknown,
            None,
        );
    }
    let checksum = raw[raw.len() - 2];
    let checksum_valid = bulk_checksum(&raw[6..raw.len() - 2]) == checksum;
    let name = raw[14];
    let Some(selector_count) = request_selector_count(name) else {
        return message(
            raw.clone(),
            MessageKind::YamahaBulkUnknown {
                midi_channel,
                direction: "dump".into(),
                data_name: name,
                opaque_tail: raw[15..raw.len() - 1].to_vec(),
                checksum: Some(checksum),
                checksum_valid: Some(checksum_valid),
            },
            Interpretation::Unknown,
            Some(checksum_valid),
        );
    };
    let body = &raw[15..raw.len() - 2];
    if body.len() < selector_count {
        return message(
            raw,
            MessageKind::Malformed {
                reason: "Bulk Dump lacks documented selector bytes".into(),
            },
            Interpretation::Unknown,
            Some(checksum_valid),
        );
    }
    let selectors = body[..selector_count].to_vec();
    if selectors.iter().any(|s| !selector_valid(name, *s, false)) {
        return message(
            raw.clone(),
            MessageKind::YamahaBulkUnknown {
                midi_channel,
                direction: "dump".into(),
                data_name: name,
                opaque_tail: raw[15..raw.len() - 1].to_vec(),
                checksum: Some(checksum),
                checksum_valid: Some(checksum_valid),
            },
            Interpretation::Unknown,
            Some(checksum_valid),
        );
    }
    let payload = body[selector_count..].to_vec();
    message(
        raw,
        MessageKind::YamahaBulkDump {
            midi_channel,
            data_name: name,
            selectors,
            raw_payload: payload,
            checksum,
            checksum_valid,
        },
        Interpretation::Documented,
        Some(checksum_valid),
    )
}
pub fn bulk_checksum(bytes_after_count_before_checksum: &[u8]) -> u8 {
    (0u8.wrapping_sub(
        bytes_after_count_before_checksum
            .iter()
            .fold(0u8, |a, b| a.wrapping_add(*b)),
    )) & 0x7f
}

fn mmc_name(cmd: u8) -> Option<&'static str> {
    match cmd {
        0x01 => Some("stop"),
        0x02 => Some("play"),
        0x03 => Some("deferred_play"),
        0x04 => Some("fast_forward"),
        0x05 => Some("rewind"),
        0x06 => Some("record_strobe"),
        0x07 => Some("record_exit"),
        0x40 => Some("write"),
        0x44 => Some("locate"),
        _ => None,
    }
}
fn parse_mmc(raw: Vec<u8>) -> ParsedMessage {
    if raw.len() < 6 || raw.get(3) != Some(&0x06) {
        return message(
            raw,
            MessageKind::UnknownSysEx {
                reason: "Universal SysEx is not MMC command 0x06".into(),
            },
            Interpretation::Unknown,
            None,
        );
    }
    let device = raw[2];
    let command = raw[4];
    let payload = raw[5..raw.len() - 1].to_vec();
    if command == 0x0d || command == 0x0f {
        return message(raw,MessageKind::AmbiguousMmcCommand{device_id:device,command,reason:"MMC Reset byte conflicts between AW2816 E1 manual p.403 table 3.4.1.1 (0x0F) and pp.405-406 section 4.13.1.8 (0x0D); unsupported".into(),raw_payload:payload},Interpretation::Conflict,None);
    }
    if let Some(name) = mmc_name(command) {
        return message(
            raw,
            MessageKind::Mmc {
                device_id: device,
                command,
                command_name: name.into(),
                raw_payload: payload,
            },
            Interpretation::Documented,
            None,
        );
    }
    message(
        raw,
        MessageKind::UnknownSysEx {
            reason: format!("unknown MMC command 0x{command:02X}"),
        },
        Interpretation::Unknown,
        None,
    )
}

/// Serialize one complete, explicit-status ordinary MIDI message.
pub fn serialize_channel_message(kind: &MessageKind) -> Result<Vec<u8>, String> {
    let mut b = Vec::new();
    match kind {
        MessageKind::ProgramChange { channel, program } if *channel < 16 && *program < 128 => {
            b.extend([0xc0 | *channel, *program])
        }
        MessageKind::ControlChange {
            channel,
            controller,
            value,
        } if *channel < 16 && *controller < 128 && *value < 128 => {
            b.extend([0xb0 | *channel, *controller, *value])
        }
        MessageKind::NoteOn {
            channel,
            note,
            velocity,
        } if *channel < 16 && *note < 128 && *velocity < 128 => {
            b.extend([0x90 | *channel, *note, *velocity])
        }
        MessageKind::NoteOff {
            channel,
            note,
            velocity,
        } if *channel < 16 && *note < 128 && *velocity < 128 => {
            b.extend([0x80 | *channel, *note, *velocity])
        }
        MessageKind::ProgramChange { .. }
        | MessageKind::ControlChange { .. }
        | MessageKind::NoteOn { .. }
        | MessageKind::NoteOff { .. } => return Err("channel/data value out of MIDI range".into()),
        _ => {
            return Err("serializer supports explicit PC, CC, Note On and Note Off messages".into())
        }
    }
    Ok(b)
}

/// Builds exactly one documented Yamaha Bulk Request; this is the sole
/// SysEx-producing helper exposed for the backup command. Manual E1 Appendix
/// pp.406-410, sections 4.13.2.2/4/6/8/10/12/14/16/18/20/22.
pub fn serialize_bulk_request(channel: u8, name: u8, selectors: &[u8]) -> Result<Vec<u8>, String> {
    if channel > 15 {
        return Err("MIDI channel must be 0..15".into());
    }
    let n = request_selector_count(name).ok_or("unsupported Bulk Request data name")?;
    if selectors.len() != n
        || selectors.iter().any(|b| *b >= 128)
        || selectors.iter().any(|b| !selector_valid(name, *b, true))
    {
        return Err("Bulk Request selectors do not match documented format".into());
    }
    let mut b = vec![0xf0, YAMAHA, 0x20 | channel, BULK_FORMAT];
    b.extend(BULK_MAGIC);
    b.push(name);
    b.extend_from_slice(selectors);
    b.push(0xf7);
    Ok(b)
}

#[derive(Clone, Copy, Debug, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum Direction {
    Input,
    Output,
}
#[derive(Clone, Debug, Serialize, Deserialize, PartialEq, Eq)]
pub struct ArchiveRecord {
    pub archive_version: u32,
    pub sequence: u64,
    pub monotonic_ns: u64,
    pub direction: Direction,
    pub source_port: String,
    pub destination_port: Option<String>,
    pub raw_midi_bytes_hex: String,
    pub parser_result: ParseBatch,
    pub parser_library_version: String,
}
impl ArchiveRecord {
    pub fn new(
        sequence: u64,
        monotonic_ns: u64,
        direction: Direction,
        source_port: String,
        destination_port: Option<String>,
        raw: &[u8],
        result: ParseBatch,
    ) -> Self {
        Self {
            archive_version: 1,
            sequence,
            monotonic_ns,
            direction,
            source_port,
            destination_port,
            raw_midi_bytes_hex: hex(raw),
            parser_result: result,
            parser_library_version: LIBRARY_VERSION.into(),
        }
    }
    pub fn raw_bytes(&self) -> Result<Vec<u8>, String> {
        unhex(&self.raw_midi_bytes_hex)
    }
}
pub fn hex(bytes: &[u8]) -> String {
    const H: &[u8] = b"0123456789abcdef";
    let mut o = String::with_capacity(bytes.len() * 2);
    for b in bytes {
        o.push(H[(b >> 4) as usize] as char);
        o.push(H[(b & 15) as usize] as char)
    }
    o
}
pub fn unhex(s: &str) -> Result<Vec<u8>, String> {
    if s.len() % 2 != 0 {
        return Err("hex byte string has odd length".into());
    }
    let mut out = Vec::with_capacity(s.len() / 2);
    for p in s.as_bytes().chunks_exact(2) {
        let hi = (p[0] as char).to_digit(16).ok_or("invalid hex")?;
        let lo = (p[1] as char).to_digit(16).ok_or("invalid hex")?;
        out.push(((hi << 4) | lo) as u8)
    }
    Ok(out)
}
pub fn reconstruct_stream(records: &[ArchiveRecord]) -> Result<Vec<u8>, String> {
    let mut r = records.to_vec();
    r.sort_by_key(|x| x.sequence);
    let mut out = Vec::new();
    for e in r {
        if e.archive_version != 1 {
            return Err(format!("unsupported archive version {}", e.archive_version));
        }
        out.extend(e.raw_bytes()?);
    }
    Ok(out)
}

pub fn parse_binary(bytes: &[u8]) -> (Vec<ParsedMessage>, Vec<ParseIssue>) {
    let mut p = StreamParser::new();
    let mut batch = p.push(bytes);
    let tail = p.finish();
    batch.messages.extend(tail.messages);
    batch.issues.extend(tail.issues);
    (batch.messages, batch.issues)
}

// Timestamp origin helper is deliberately owned by the control tool, never audio.
pub fn elapsed_ns(origin: Instant) -> u64 {
    origin.elapsed().as_nanos().min(u64::MAX as u128) as u64
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn pc_cc_round_trip() {
        for k in [
            MessageKind::ProgramChange {
                channel: 4,
                program: 70,
            },
            MessageKind::ControlChange {
                channel: 2,
                controller: 11,
                value: 127,
            },
        ] {
            let b = serialize_channel_message(&k).unwrap();
            let (m, e) = parse_binary(&b);
            assert!(e.is_empty());
            assert_eq!(m[0].kind, k);
        }
    }
    #[test]
    fn fragmented_sysex_and_realtime_interleave() {
        let mut p = StreamParser::new();
        let a = p.push(&[0xf0, 0x43, 0x10, 0x3e]);
        assert!(a.messages.is_empty());
        let b = p.push(&[0x07, 0x10, 0x00, 0xf8, 0x00, 0xf7]);
        assert_eq!(b.messages.len(), 2);
        assert!(matches!(
            b.messages[0].kind,
            MessageKind::Realtime { status: 0xf8 }
        ));
        assert!(matches!(
            b.messages[1].kind,
            MessageKind::YamahaParameterChange { .. }
        ));
        assert!(p.finish().issues.is_empty());
    }
    #[test]
    fn multiple_messages_and_running_status() {
        let (m, e) = parse_binary(&[0xc0, 4, 0xc1, 5, 0xb0, 7, 100, 8, 101]);
        assert!(e.is_empty());
        assert_eq!(m.len(), 4);
        assert!(matches!(
            m[3].kind,
            MessageKind::ControlChange {
                controller: 8,
                value: 101,
                ..
            }
        ));
    }
    #[test]
    fn truncated_sysex_and_midi_safe() {
        let (m, e) = parse_binary(&[0xf0, 0x43, 0x10, 0x3e, 0x07]);
        assert!(m.is_empty());
        assert_eq!(e[0].raw_midi_bytes, [0xf0, 0x43, 0x10, 0x3e, 0x07]);
        for n in 0..500 {
            let data = (0..n)
                .map(|x| ((x * 37 + n * 13) & 255) as u8)
                .collect::<Vec<_>>();
            let _ = parse_binary(&data);
        }
    }
    #[test]
    fn bounded_sysex_unknown_payload_and_archive_json_round_trip() {
        let unknown = [0xf0, 0x43, 0x10, 0x3e, 0x07, 0x7f, 0x12, 0xf7];
        let (messages, issues) = parse_binary(&unknown);
        assert!(issues.is_empty());
        assert_eq!(messages[0].raw_midi_bytes, unknown);
        assert_eq!(messages[0].interpretation, Interpretation::Unknown);

        let raw = [0xf0, 0x43, 0x10, 0x3e, 0x07, 0x10, 0xf8, 0x01, 0xf7];
        let mut parser = StreamParser::new();
        let mut records = Vec::new();
        for (sequence, chunk) in raw.chunks(2).enumerate() {
            records.push(ArchiveRecord::new(
                sequence as u64,
                sequence as u64 * 1_000,
                Direction::Input,
                "synthetic fixture".into(),
                None,
                chunk,
                parser.push(chunk),
            ));
        }
        let json_lines = records
            .iter()
            .map(serde_json::to_string)
            .collect::<Result<Vec<_>, _>>()
            .unwrap();
        let decoded = json_lines
            .iter()
            .map(|line| serde_json::from_str::<ArchiveRecord>(line).unwrap())
            .collect::<Vec<_>>();
        assert_eq!(reconstruct_stream(&decoded).unwrap(), raw);

        let mut oversized = vec![0xf0];
        oversized.resize(MAX_SYSEX_BYTES + 2, 0x01);
        oversized.push(0xf7);
        let (_, issues) = parse_binary(&oversized);
        assert!(issues.iter().any(|issue| issue.reason.contains("limit")));
        assert!(issues
            .iter()
            .all(|issue| issue.raw_midi_bytes.len() <= MAX_SYSEX_BYTES + 1));
    }
    #[test]
    fn wrong_yamaha_ids_are_unknown() {
        for b in [
            vec![0xf0, 0x42, 0x10, 0x3e, 7, 0, 0xf7],
            vec![0xf0, 0x43, 0x10, 0x3d, 7, 0, 0xf7],
            vec![0xf0, 0x43, 0x10, 0x3e, 6, 0, 0xf7],
        ] {
            let (m, _) = parse_binary(&b);
            assert!(!matches!(
                m[0].kind,
                MessageKind::YamahaParameterChange { .. }
            ));
        }
    }
    fn bulk_fixture() -> Vec<u8> {
        let mut b = vec![0xf0, 0x43, 0x00, 0x7e, 0, 0];
        b.extend(BULK_MAGIC);
        b.push(b'P');
        b.push(b' ');
        b.extend(0..128u8);
        let sum = bulk_checksum(&b[6..]);
        let count = (b.len() - 6 + 1) as u16;
        b[4] = (count >> 7) as u8;
        b[5] = (count & 0x7f) as u8;
        b.push(sum);
        b.push(0xf7);
        b
    }
    #[test]
    fn bulk_checksum_and_invalid_checksum() {
        let b = bulk_fixture();
        let (m, e) = parse_binary(&b);
        assert!(e.is_empty());
        assert!(matches!(
            m[0].kind,
            MessageKind::YamahaBulkDump {
                checksum_valid: true,
                ..
            }
        ));
        let mut bad = b;
        let i = bad.len() - 2;
        bad[i] ^= 1;
        let (m, _) = parse_binary(&bad);
        assert!(matches!(
            m[0].kind,
            MessageKind::YamahaBulkDump {
                checksum_valid: false,
                ..
            }
        ));
        assert_eq!(m[0].checksum_passed, Some(false));
    }
    #[test]
    fn bulk_requests_serialize_parse_and_only_known_names() {
        for (name, s) in [
            (b'S', vec![]),
            (b'M', vec![12]),
            (b'R', vec![3]),
            (b'Q', vec![127]),
            (b'Y', vec![127]),
            (b'E', vec![127]),
            (b'T', vec![20]),
            (b'H', vec![64]),
            (b'A', vec![16]),
            (b'P', vec![]),
            (b'C', vec![]),
        ] {
            let b = serialize_bulk_request(0, name, &s).unwrap();
            let (m, e) = parse_binary(&b);
            assert!(e.is_empty());
            assert!(
                matches!(&m[0].kind,MessageKind::YamahaBulkRequest{data_name,selectors,..}if *data_name==name&&*selectors==s)
            );
        }
    }
    #[test]
    fn mmc_reset_conflict_never_classified() {
        for command in [0x0d, 0x0f] {
            let b = [0xf0, 0x7f, 0x7f, 0x06, command, 0xf7];
            let (m, _) = parse_binary(&b);
            assert!(
                matches!(m[0].kind,MessageKind::AmbiguousMmcCommand{command:c,..}if c==command)
            );
            assert_eq!(m[0].interpretation, Interpretation::Conflict);
            assert_eq!(m[0].serialize_exact(), b);
        }
    }
    #[test]
    fn archive_reconstruction_exact() {
        let raw = [0xc0, 8, 0xf0, 0x43, 0xf8, 0x10, 0xf7, 0xb0, 1, 2];
        let mut p = StreamParser::new();
        let mut records = vec![];
        let origin = Instant::now();
        for (i, c) in raw.chunks(3).enumerate() {
            records.push(ArchiveRecord::new(
                i as u64,
                elapsed_ns(origin),
                Direction::Input,
                "synthetic MIDI fixture".into(),
                None,
                c,
                p.push(c),
            ));
        }
        let tail = p.finish();
        if !tail.issues.is_empty() {
            records.push(ArchiveRecord::new(
                records.len() as u64,
                elapsed_ns(origin),
                Direction::Input,
                "synthetic MIDI fixture".into(),
                None,
                &[],
                tail,
            ));
        }
        assert_eq!(reconstruct_stream(&records).unwrap(), raw);
    }
}
