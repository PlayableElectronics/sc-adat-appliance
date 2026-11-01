use anyhow::{anyhow, Context, Result};
use aw2816_protocol::{
    elapsed_ns, parse_binary, serialize_bulk_request, ArchiveRecord, Direction, MessageKind,
    ParseBatch, ParsedMessage, StreamParser, LIBRARY_VERSION,
};
use clap::{Parser, Subcommand};
use midir::{Ignore, MidiInput, MidiInputPort, MidiOutput, MidiOutputPort};
use serde::{Deserialize, Serialize};
use std::{
    fs::{self, File, OpenOptions},
    io::{BufRead, BufReader, Read, Write},
    path::{Path, PathBuf},
    sync::{
        atomic::{AtomicBool, Ordering},
        mpsc,
    },
    time::{Duration, Instant},
};

#[derive(Parser)]
#[command(
    name = "aw2816ctl",
    about = "Offline-first Yamaha AW2816 MIDI inspection and backup"
)]
struct Args {
    #[command(subcommand)]
    command: Command,
}
#[derive(Subcommand)]
enum Command {
    Ports,
    Monitor {
        #[arg(long)]
        input: String,
        #[arg(long)]
        output: Option<PathBuf>,
    },
    Decode {
        file: PathBuf,
    },
    Inspect {
        path: PathBuf,
    },
    Diff {
        path_a: PathBuf,
        path_b: PathBuf,
    },
    Backup {
        #[arg(long)]
        input: String,
        #[arg(long)]
        output: PathBuf,
        #[arg(long)]
        output_port: Option<String>,
        #[arg(long, default_value = "1")]
        channel: u8,
        #[arg(long, default_value = "300")]
        quiet_ms: u64,
    },
    ValidatePreset {
        path: PathBuf,
    },
}

#[derive(Clone, Debug, Serialize, Deserialize)]
struct ArchiveHeader {
    archive_version: u32,
    parser_library_version: String,
    capture_started_monotonic_ns: u64,
    synthetic: bool,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct CombinedPreset {
    schema_version: u32,
    preset_id: String,
    authoritative: DesiredState,
    captured_yamaha: CapturedYamahaState,
    generated_yamaha_artifact: GeneratedArtifact,
    hardware_confirmation: HardwareConfirmation,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct DesiredState {
    signature_dsp: SignatureDspPresetRef,
    yamaha: YamahaDesiredState,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct SignatureDspPresetRef {
    preset_id: String,
    schema_version: u32,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct YamahaDesiredState {
    scene_number: Option<u8>,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct CapturedYamahaState {
    archive: String,
    captured_from_port: String,
    capture_sha256: Option<String>,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct GeneratedArtifact {
    kind: String,
    scene_number: Option<u8>,
    artifact_id: Option<String>,
    source_preset_id: String,
}
#[derive(Clone, Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
struct HardwareConfirmation {
    status: String,
    confirmed_on: String,
    notes: String,
}

fn main() -> Result<()> {
    match Args::parse().command {
        Command::Ports => ports(),
        Command::Monitor { input, output } => monitor(&input, output.as_deref()),
        Command::Decode { file } => decode(&file, false),
        Command::Inspect { path } => decode(&path, true),
        Command::Diff { path_a, path_b } => diff(&path_a, &path_b),
        Command::Backup {
            input,
            output,
            output_port,
            channel,
            quiet_ms,
        } => backup(&input, &output, output_port.as_deref(), channel, quiet_ms),
        Command::ValidatePreset { path } => {
            let bytes = fs::read(path)?;
            let p: CombinedPreset = serde_json::from_slice(&bytes)?;
            validate_preset(&p)?;
            println!(
                "combined preset valid (schema version {})",
                p.schema_version
            );
            Ok(())
        }
    }
}

fn ports() -> Result<()> {
    let input = MidiInput::new("aw2816ctl ports input")?;
    println!("MIDI input ports:");
    for (i, p) in input.ports().iter().enumerate() {
        println!("  {i}: {}", input.port_name(p)?);
    }
    let output = MidiOutput::new("aw2816ctl ports output")?;
    println!("MIDI output ports:");
    for (i, p) in output.ports().iter().enumerate() {
        println!("  {i}: {}", output.port_name(p)?);
    }
    Ok(())
}

fn resolve_input(input: &MidiInput, selector: &str) -> Result<MidiInputPort> {
    let ps = input.ports();
    if let Ok(i) = selector.parse::<usize>() {
        return ps
            .get(i)
            .cloned()
            .ok_or_else(|| anyhow!("MIDI input port index {i} does not exist"));
    }
    let found = ps
        .into_iter()
        .filter(|p| input.port_name(p).is_ok_and(|n| n == selector))
        .collect::<Vec<_>>();
    if found.len() != 1 {
        return Err(anyhow!(
            "input port name must match exactly one MIDI input; found {}",
            found.len()
        ));
    }
    Ok(found[0].clone())
}
fn resolve_output(output: &MidiOutput, selector: &str) -> Result<MidiOutputPort> {
    let ps = output.ports();
    if let Ok(i) = selector.parse::<usize>() {
        return ps
            .get(i)
            .cloned()
            .ok_or_else(|| anyhow!("MIDI output port index {i} does not exist"));
    }
    let found = ps
        .into_iter()
        .filter(|p| output.port_name(p).is_ok_and(|n| n == selector))
        .collect::<Vec<_>>();
    if found.len() != 1 {
        return Err(anyhow!(
            "output port name must match exactly one MIDI output; found {}",
            found.len()
        ));
    }
    Ok(found[0].clone())
}

fn write_record(file: &mut File, record: &ArchiveRecord) -> Result<()> {
    serde_json::to_writer(&mut *file, record)?;
    file.write_all(b"\n")?;
    Ok(())
}
fn batch_for(parser: &mut StreamParser, raw: &[u8]) -> ParseBatch {
    parser.push(raw)
}
fn print_batch(seq: u64, b: &ParseBatch) {
    for m in &b.messages {
        println!("{seq}: {}", summary(m));
    }
    for e in &b.issues {
        println!(
            "{seq}: malformed {} bytes: {}",
            e.raw_midi_bytes.len(),
            e.reason
        );
    }
}

fn monitor(selector: &str, output_path: Option<&Path>) -> Result<()> {
    let mut midi = MidiInput::new("aw2816ctl passive monitor")?;
    midi.ignore(Ignore::None);
    let port = resolve_input(&midi, selector)?;
    let port_name = midi.port_name(&port)?;
    let (tx, rx) = mpsc::channel::<(u64, Vec<u8>)>();
    let origin = Instant::now();
    let callback_origin = origin;
    let _connection = midi.connect(
        &port,
        "aw2816ctl passive input",
        move |_, bytes, _| {
            let _ = tx.send((elapsed_ns(callback_origin), bytes.to_vec()));
        },
        (),
    )?;
    let generated;
    let capture_path = if let Some(p) = output_path {
        p
    } else {
        generated = PathBuf::from(format!(
            "aw2816-capture-{}.jsonl",
            std::time::SystemTime::now()
                .duration_since(std::time::UNIX_EPOCH)?
                .as_nanos()
        ));
        &generated
    };
    let mut file = OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(capture_path)
        .with_context(|| {
            format!(
                "creating lossless capture {} (refusing to overwrite)",
                capture_path.display()
            )
        })?;
    let mut parser = StreamParser::new();
    let running = std::sync::Arc::new(AtomicBool::new(true));
    let stop = running.clone();
    ctrlc::set_handler(move || stop.store(false, Ordering::Relaxed))
        .context("installing Ctrl-C handler")?;
    println!("Passive monitor on {port_name}; no MIDI output is opened. Lossless JSONL capture: {}. Ctrl-C to stop.",capture_path.display());
    let mut seq = 0u64;
    while running.load(Ordering::Relaxed) {
        match rx.recv_timeout(Duration::from_millis(100)) {
            Ok((ns, raw)) => {
                let batch = batch_for(&mut parser, &raw);
                let record = ArchiveRecord::new(
                    seq,
                    ns,
                    Direction::Input,
                    port_name.clone(),
                    Some("aw2816ctl passive monitor".into()),
                    &raw,
                    batch.clone(),
                );
                write_record(&mut file, &record)?;
                print_batch(seq, &batch);
                seq += 1;
            }
            Err(mpsc::RecvTimeoutError::Timeout) => {}
            Err(mpsc::RecvTimeoutError::Disconnected) => break,
        }
    }
    let tail = parser.finish();
    if !tail.issues.is_empty() {
        let empty = ArchiveRecord::new(
            seq,
            elapsed_ns(origin),
            Direction::Input,
            port_name,
            Some("aw2816ctl passive monitor".into()),
            &[],
            tail.clone(),
        );
        write_record(&mut file, &empty)?;
        print_batch(seq, &tail);
    }
    Ok(())
}

fn load_records(path: &Path) -> Result<Option<Vec<ArchiveRecord>>> {
    let p = if path.is_dir() {
        let q = path.join("events.jsonl");
        if !q.exists() {
            return Ok(None);
        }
        q
    } else {
        path.to_path_buf()
    };
    let mut f = File::open(&p)?;
    let mut first = String::new();
    BufReader::new(&mut f).read_line(&mut first)?;
    if !first.trim_start().starts_with('{') || !first.contains("archive_version") {
        return Ok(None);
    }
    drop(f);
    let reader = BufReader::new(File::open(&p)?);
    let mut records = Vec::new();
    for (i, line) in reader.lines().enumerate() {
        let line = line?;
        if line.trim().is_empty() {
            continue;
        }
        let r: ArchiveRecord = serde_json::from_str(&line)
            .with_context(|| format!("parsing archive record line {}", i + 1))?;
        if r.archive_version != 1 {
            return Err(anyhow!("unsupported archive version {}", r.archive_version));
        }
        records.push(r);
    }
    Ok(Some(records))
}
fn records_messages(records: &[ArchiveRecord]) -> Vec<(u64, ParsedMessage)> {
    let mut out = Vec::new();
    for r in records {
        for m in &r.parser_result.messages {
            out.push((r.sequence, m.clone()));
        }
    }
    out
}
fn decode(path: &Path, verbose: bool) -> Result<()> {
    if let Some(records) = load_records(path)? {
        for (seq, m) in records_messages(&records) {
            if verbose {
                println!("{}", serde_json::to_string_pretty(&inspect_document(&m))?);
            } else {
                println!(
                    "{seq}: {} raw={}",
                    summary(&m),
                    aw2816_protocol::hex(&m.raw_midi_bytes)
                );
            }
        }
        for r in &records {
            for e in &r.parser_result.issues {
                println!(
                    "{}: malformed raw={} reason={}",
                    r.sequence,
                    aw2816_protocol::hex(&e.raw_midi_bytes),
                    e.reason
                );
            }
        }
        return Ok(());
    }
    let mut bytes = Vec::new();
    File::open(path)?.read_to_end(&mut bytes)?;
    let (messages, issues) = parse_binary(&bytes);
    for (i, m) in messages.iter().enumerate() {
        if verbose {
            println!("{}", serde_json::to_string_pretty(&inspect_document(m))?);
        } else {
            println!(
                "{i}: {} raw={}",
                summary(m),
                aw2816_protocol::hex(&m.raw_midi_bytes)
            );
        }
    }
    for e in issues {
        println!(
            "malformed raw={} reason={}",
            aw2816_protocol::hex(&e.raw_midi_bytes),
            e.reason
        );
    }
    Ok(())
}

fn inspect_document(m: &ParsedMessage) -> serde_json::Value {
    let unknown = match &m.kind {
        MessageKind::YamahaParameterChange { raw_data, .. }
        | MessageKind::YamahaBulkDump {
            raw_payload: raw_data,
            ..
        } => aw2816_protocol::hex(raw_data),
        MessageKind::YamahaBulkUnknown { opaque_tail, .. } => aw2816_protocol::hex(opaque_tail),
        MessageKind::UnknownSysEx { .. }
        | MessageKind::AmbiguousMmcCommand { .. }
        | MessageKind::Unknown { .. }
        | MessageKind::Malformed { .. } => aw2816_protocol::hex(&m.raw_midi_bytes),
        _ => String::new(),
    };
    serde_json::json!({"message_type":format!("{}",summary(m)),"length_bytes":logical_length(m),"raw_event_length_bytes":m.raw_midi_bytes.len(),"checksum_passed":m.checksum_passed,"interpretation":m.interpretation,"known_fields":m.kind,"unknown_bytes_hex":unknown,"raw_midi_bytes_hex":aw2816_protocol::hex(&m.raw_midi_bytes)})
}
fn logical_length(m: &ParsedMessage) -> usize {
    match m.kind {
        MessageKind::ProgramChange { .. }
        | MessageKind::ChannelPressure { .. }
        | MessageKind::MtcQuarterFrame { .. } => 2,
        MessageKind::ControlChange { .. }
        | MessageKind::NoteOn { .. }
        | MessageKind::NoteOff { .. }
        | MessageKind::PolyPressure { .. }
        | MessageKind::PitchBend { .. }
        | MessageKind::SongPositionPointer { .. } => 3,
        _ => m.raw_midi_bytes.len(),
    }
}

fn summary(m: &ParsedMessage) -> String {
    match &m.kind{
    MessageKind::ProgramChange{channel,program}=>format!("Program Change channel={} program={program}",channel+1),
    MessageKind::ControlChange{channel,controller,value}=>format!("Control Change channel={} controller={controller} value={value}",channel+1),
    MessageKind::YamahaParameterChange{midi_channel,mode,parameter_type,family,raw_data}=>format!("AW2816 Parameter Change channel={} mode={mode} type=0x{parameter_type:02X} family={family:?} raw_data={}",midi_channel+1,aw2816_protocol::hex(raw_data)),
    MessageKind::YamahaBulkDump{midi_channel,data_name,selectors,raw_payload,checksum,checksum_valid}=>format!("AW2816 Bulk Dump channel={} name={} selectors={} payload={} checksum=0x{checksum:02X} passed={checksum_valid}",midi_channel+1,name(*data_name),aw2816_protocol::hex(selectors),raw_payload.len()),
    MessageKind::YamahaBulkRequest{midi_channel,data_name,selectors}=>format!("AW2816 Bulk Request channel={} name={} selectors={}",midi_channel+1,name(*data_name),aw2816_protocol::hex(selectors)),
    MessageKind::Mmc{device_id,command,command_name,raw_payload}=>format!("MMC device=0x{device_id:02X} command=0x{command:02X} {command_name} payload={}",aw2816_protocol::hex(raw_payload)),
    MessageKind::AmbiguousMmcCommand{device_id,command,reason,..}=>format!("AMBIGUOUS MMC device=0x{device_id:02X} command=0x{command:02X}: {reason}"),
    other=>format!("{other:?}")}
}
fn name(b: u8) -> String {
    if b.is_ascii_graphic() {
        (b as char).to_string()
    } else {
        format!("0x{b:02X}")
    }
}

fn diff(a: &Path, b: &Path) -> Result<()> {
    let left = read_messages(a)?;
    let right = read_messages(b)?;
    let n = left.len().max(right.len());
    for i in 0..n {
        match (left.get(i), right.get(i)) {
            (Some(l), Some(r)) => {
                if semantic_key(&l.kind) == semantic_key(&r.kind) {
                    if l.kind == r.kind && l.raw_midi_bytes == r.raw_midi_bytes {
                        continue;
                    }
                    let ranges = byte_ranges(&l.raw_midi_bytes, &r.raw_midi_bytes);
                    println!(
                        "message {i}: semantic match {}; raw byte ranges differ {}",
                        summary(l),
                        format_ranges(&ranges)
                    );
                } else {
                    println!(
                        "message {i}: semantic change [{}] -> [{}]; unknown byte ranges {}",
                        summary(l),
                        summary(r),
                        format_ranges(&byte_ranges(&l.raw_midi_bytes, &r.raw_midi_bytes))
                    );
                }
            }
            (Some(l), None) => println!("message {i}: removed [{}]", summary(l)),
            (None, Some(r)) => println!("message {i}: added [{}]", summary(r)),
            _ => {}
        }
    }
    Ok(())
}
fn read_messages(path: &Path) -> Result<Vec<ParsedMessage>> {
    if let Some(records) = load_records(path)? {
        return Ok(records_messages(&records)
            .into_iter()
            .map(|x| x.1)
            .collect());
    }
    let mut b = Vec::new();
    File::open(path)?.read_to_end(&mut b)?;
    Ok(parse_binary(&b).0)
}
fn semantic_key(k: &MessageKind) -> String {
    match k {
        MessageKind::ProgramChange { channel, .. } => format!("pc:{channel}"),
        MessageKind::ControlChange {
            channel,
            controller,
            ..
        } => format!("cc:{channel}:{controller}"),
        MessageKind::YamahaParameterChange {
            midi_channel,
            mode,
            parameter_type,
            ..
        } => format!("param:{midi_channel}:{mode}:{parameter_type}"),
        MessageKind::YamahaBulkDump {
            midi_channel,
            data_name,
            selectors,
            ..
        } => format!(
            "dump:{midi_channel}:{data_name}:{}",
            aw2816_protocol::hex(selectors)
        ),
        MessageKind::YamahaBulkRequest {
            midi_channel,
            data_name,
            selectors,
        } => format!(
            "request:{midi_channel}:{data_name}:{}",
            aw2816_protocol::hex(selectors)
        ),
        _ => format!("raw:{:?}", k),
    }
}
fn byte_ranges(a: &[u8], b: &[u8]) -> Vec<(usize, usize)> {
    let n = a.len().max(b.len());
    let mut ranges = Vec::new();
    let mut start = None;
    for i in 0..n {
        let diff = a.get(i) != b.get(i);
        match (diff, start) {
            (true, None) => start = Some(i),
            (false, Some(s)) => {
                ranges.push((s, i));
                start = None
            }
            _ => {}
        }
    }
    if let Some(s) = start {
        ranges.push((s, n));
    }
    ranges
}
fn format_ranges(r: &[(usize, usize)]) -> String {
    if r.is_empty() {
        "none".into()
    } else {
        r.iter()
            .map(|(a, b)| format!("[{a}..{b})"))
            .collect::<Vec<_>>()
            .join(",")
    }
}

fn request_plan(channel: u8) -> Result<Vec<Vec<u8>>> {
    let mut v = Vec::new();
    let mut add = |name: u8, selector: Option<u8>| -> Result<()> {
        v.push(
            serialize_bulk_request(channel, name, &selector.into_iter().collect::<Vec<_>>())
                .map_err(anyhow::Error::msg)?,
        );
        Ok(())
    };
    for s in 0..=97 {
        add(b'M', Some(s))?;
    }
    add(b'M', Some(127))?;
    add(b'S', None)?;
    for s in 0..=3 {
        add(b'R', Some(s))?;
    }
    for (n, max) in [
        (b'Q', 127),
        (b'Y', 127),
        (b'E', 127),
        (b'T', 20),
        (b'H', 64),
        (b'A', 16),
    ] {
        for s in 0..=max {
            add(n, Some(s as u8))?;
        }
    }
    add(b'P', None)?;
    add(b'C', None)?;
    Ok(v)
}
fn backup(
    input_selector: &str,
    dir: &Path,
    output_selector: Option<&str>,
    channel: u8,
    quiet_ms: u64,
) -> Result<()> {
    if !(1..=16).contains(&channel) {
        return Err(anyhow!("--channel must be 1..16"));
    }
    let ch = channel - 1;
    fs::create_dir_all(dir)?;
    let mut midi_in = MidiInput::new("aw2816ctl backup input")?;
    midi_in.ignore(Ignore::None);
    let in_port = resolve_input(&midi_in, input_selector)?;
    let in_name = midi_in.port_name(&in_port)?;
    let midi_out = MidiOutput::new("aw2816ctl documented bulk requester")?;
    let out_selector = output_selector
        .map(str::to_owned)
        .or_else(|| Some(in_name.clone()));
    let out_selector = out_selector.ok_or_else(|| anyhow!("provide --output-port"))?;
    let out_port = resolve_output(&midi_out, &out_selector).with_context(|| {
        format!("finding paired MIDI output for input {in_name}; use --output-port")
    })?;
    let out_name = midi_out.port_name(&out_port)?;
    let (tx, rx) = mpsc::channel::<(u64, Vec<u8>)>();
    let origin = Instant::now();
    let cb_origin = origin;
    let _input = midi_in.connect(
        &in_port,
        "aw2816ctl backup listener",
        move |_, bytes, _| {
            let _ = tx.send((elapsed_ns(cb_origin), bytes.to_vec()));
        },
        (),
    )?;
    let mut output = midi_out.connect(&out_port, "aw2816ctl bulk requests")?;
    let mut events = create_new(dir.join("events.jsonl"))?;
    let mut raw_in = create_new(dir.join("raw-input.bin"))?;
    let mut raw_out = create_new(dir.join("raw-output.bin"))?;
    let requests = request_plan(ch)?;
    let mut seq = 0u64;
    let mut parser = StreamParser::new();
    let quiet = Duration::from_millis(quiet_ms.max(10));
    for (index, request) in requests.iter().enumerate() {
        let parsed = parse_binary(request).0;
        if !parsed
            .iter()
            .all(|m| matches!(m.kind, MessageKind::YamahaBulkRequest { .. }))
        {
            return Err(anyhow!(
                "internal safety check refused non-Bulk-Request output"
            ));
        }
        output
            .send(request)
            .context("sending documented Bulk Request")?;
        raw_out.write_all(request)?;
        let b = ParseBatch {
            messages: parsed,
            issues: vec![],
        };
        write_archive_pair(
            &mut events,
            ArchiveRecord::new(
                seq,
                elapsed_ns(origin),
                Direction::Output,
                "host MIDI output".into(),
                Some(out_name.clone()),
                request,
                b,
            ),
        )?;
        seq += 1;
        let deadline = Instant::now() + quiet;
        let mut got = 0usize;
        while Instant::now() < deadline {
            let rem = deadline.saturating_duration_since(Instant::now());
            match rx.recv_timeout(rem) {
                Ok((ns, bytes)) => {
                    raw_in.write_all(&bytes)?;
                    let batch = parser.push(&bytes);
                    got += batch.messages.len();
                    write_archive_pair(
                        &mut events,
                        ArchiveRecord::new(
                            seq,
                            ns,
                            Direction::Input,
                            in_name.clone(),
                            Some("host MIDI input".into()),
                            &bytes,
                            batch,
                        ),
                    )?;
                    seq += 1;
                }
                Err(_) => break,
            }
        }
        println!(
            "request {}/{} name={} received_messages={got}",
            index + 1,
            requests.len(),
            name(request[12])
        );
    }
    raw_in.flush()?;
    raw_out.flush()?;
    let tail = parser.finish();
    if !tail.issues.is_empty() {
        write_archive_pair(
            &mut events,
            ArchiveRecord::new(
                seq,
                elapsed_ns(origin),
                Direction::Input,
                in_name.clone(),
                Some("host MIDI input".into()),
                &[],
                tail,
            ),
        )?;
    }
    let header = ArchiveHeader {
        archive_version: 1,
        parser_library_version: LIBRARY_VERSION.into(),
        capture_started_monotonic_ns: 0,
        synthetic: false,
    };
    serde_json::to_writer_pretty(create_new(dir.join("manifest.json"))?, &header)?;
    println!("Backup captured {} documented Bulk Request messages. Raw directions saved separately under {}",requests.len(),dir.display());
    Ok(())
}

fn create_new(path: impl AsRef<Path>) -> Result<File> {
    let p = path.as_ref();
    OpenOptions::new()
        .write(true)
        .create_new(true)
        .open(p)
        .with_context(|| format!("creating {} (refusing to overwrite)", p.display()))
}
fn write_archive_pair(f: &mut File, record: ArchiveRecord) -> Result<()> {
    serde_json::to_writer(&mut *f, &record)?;
    f.write_all(b"\n")?;
    Ok(())
}

fn validate_preset(p: &CombinedPreset) -> Result<()> {
    if p.schema_version != 1 {
        return Err(anyhow!("schema_version must be 1"));
    }
    if p.preset_id.trim().is_empty() || p.authoritative.signature_dsp.preset_id.trim().is_empty() {
        return Err(anyhow!("preset identifiers must be non-empty"));
    }
    if p.authoritative.signature_dsp.schema_version != 1 {
        return Err(anyhow!("unsupported signature DSP preset schema"));
    }
    if p.authoritative
        .yamaha
        .scene_number
        .is_some_and(|n| !(1..=96).contains(&n))
    {
        return Err(anyhow!("desired scene number must be 1..96"));
    }
    if p.generated_yamaha_artifact
        .scene_number
        .is_some_and(|n| !(1..=96).contains(&n))
    {
        return Err(anyhow!("generated artifact scene must be 1..96"));
    }
    if p.generated_yamaha_artifact.source_preset_id != p.preset_id {
        return Err(anyhow!(
            "generated artifact source_preset_id must match preset_id"
        ));
    }
    if !["pending", "confirmed", "rejected"].contains(&p.hardware_confirmation.status.as_str()) {
        return Err(anyhow!(
            "hardware_confirmation.status must be pending, confirmed or rejected"
        ));
    }
    if p.captured_yamaha.archive.trim().is_empty() {
        return Err(anyhow!(
            "captured_yamaha.archive is required; use an explicit not-yet-captured path"
        ));
    }
    if p.captured_yamaha.captured_from_port.trim().is_empty() {
        return Err(anyhow!(
            "captured_yamaha.captured_from_port must be non-empty"
        ));
    }
    if p.captured_yamaha.capture_sha256.as_ref().is_some_and(|s| {
        s.len() != 64
            || !s
                .bytes()
                .all(|b| b.is_ascii_hexdigit() && !b.is_ascii_uppercase())
    }) {
        return Err(anyhow!(
            "capture_sha256 must be 64 lowercase hex characters"
        ));
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn diff_is_deterministic() {
        let a = [0xc0, 1, 0xb0, 2, 3];
        let b = [0xc0, 2, 0xb0, 2, 4];
        let ma = parse_binary(&a).0;
        let mb = parse_binary(&b).0;
        assert_eq!(
            format_ranges(&byte_ranges(&ma[0].raw_midi_bytes, &mb[0].raw_midi_bytes)),
            "[1..2)"
        );
        assert_eq!(semantic_key(&ma[1].kind), semantic_key(&mb[1].kind));
    }
    #[test]
    fn preset_validation_accepts_pending_and_rejects_bad_scene() {
        let p = CombinedPreset {
            schema_version: 1,
            preset_id: "show-a".into(),
            authoritative: DesiredState {
                signature_dsp: SignatureDspPresetRef {
                    preset_id: "rust-a".into(),
                    schema_version: 1,
                },
                yamaha: YamahaDesiredState {
                    scene_number: Some(4),
                },
            },
            captured_yamaha: CapturedYamahaState {
                archive: "not-yet-captured/events.jsonl".into(),
                captured_from_port: "unconfirmed".into(),
                capture_sha256: None,
            },
            generated_yamaha_artifact: GeneratedArtifact {
                kind: "scene_bulk_dump".into(),
                scene_number: Some(4),
                artifact_id: None,
                source_preset_id: "show-a".into(),
            },
            hardware_confirmation: HardwareConfirmation {
                status: "pending".into(),
                confirmed_on: "".into(),
                notes: "synthetic schema fixture".into(),
            },
        };
        assert!(validate_preset(&p).is_ok());
        let mut bad = p;
        bad.generated_yamaha_artifact.scene_number = Some(97);
        assert!(validate_preset(&bad).is_err());
    }
    #[test]
    fn backup_plan_only_emits_documented_requests() {
        let plan = request_plan(0).unwrap();
        assert!(plan.len() > 500);
        for request in plan {
            let (m, e) = parse_binary(&request);
            assert!(e.is_empty());
            assert!(matches!(m[0].kind, MessageKind::YamahaBulkRequest { .. }));
            assert!(request.starts_with(&[0xf0, 0x43, 0x20, 0x7e]));
        }
    }
}
