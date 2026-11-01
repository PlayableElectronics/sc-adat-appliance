use crate::{
    config::Config,
    core::{Processor, SharedMeters},
    INPUT_CHANNELS, OUTPUT_CHANNELS, SAMPLE_RATE,
};
use anyhow::{anyhow, Context, Result};
use cpal::traits::{DeviceTrait, HostTrait, StreamTrait};
use cpal::{Device, SampleFormat, StreamConfig};
use rtrb::{Consumer, Producer, RingBuffer};
use std::sync::{
    atomic::{AtomicU64, Ordering},
    Arc,
};
use std::time::Instant;

pub struct Diagnostics {
    pub input_overflow: AtomicU64,
    pub output_underflow: AtomicU64,
    pub input_discontinuities: AtomicU64,
    pub output_discontinuities: AtomicU64,
    pub largest_dsp_ns: AtomicU64,
    pub input_callback_min_frames: AtomicU64,
    pub input_callback_max_frames: AtomicU64,
    pub output_callback_min_frames: AtomicU64,
    pub output_callback_max_frames: AtomicU64,
}
impl Default for Diagnostics {
    fn default() -> Self {
        Self {
            input_overflow: AtomicU64::new(0),
            output_underflow: AtomicU64::new(0),
            input_discontinuities: AtomicU64::new(0),
            output_discontinuities: AtomicU64::new(0),
            largest_dsp_ns: AtomicU64::new(0),
            input_callback_min_frames: AtomicU64::new(u64::MAX),
            input_callback_max_frames: AtomicU64::new(0),
            output_callback_min_frames: AtomicU64::new(u64::MAX),
            output_callback_max_frames: AtomicU64::new(0),
        }
    }
}
pub struct LiveStreams {
    _input: cpal::Stream,
    _output: cpal::Stream,
    pub meters: Arc<SharedMeters>,
    pub diagnostics: Arc<Diagnostics>,
    pub input_config: StreamConfig,
    pub output_config: StreamConfig,
    pub buffering_frames: usize,
}
pub fn list_devices() -> Result<Vec<(String, Device)>> {
    let host = cpal::default_host();
    let mut out = Vec::new();
    for d in host.devices()? {
        let name = d.name().unwrap_or_else(|_| "<unnamed>".into());
        out.push((name, d));
    }
    Ok(out)
}
pub fn inspect_device(device: &Device) -> Result<String> {
    let mut s = format!("Device: {}\n", device.name()?);
    s.push_str("Input configurations:\n");
    match device.supported_input_configs() {
        Ok(configs) => {
            for c in configs {
                s.push_str(&format!(
                    "  {} ch, {:?}, {}-{} Hz\n",
                    c.channels(),
                    c.sample_format(),
                    c.min_sample_rate().0,
                    c.max_sample_rate().0
                ));
            }
        }
        Err(e) => s.push_str(&format!("  unavailable: {e}\n")),
    }
    s.push_str("Output configurations:\n");
    match device.supported_output_configs() {
        Ok(configs) => {
            for c in configs {
                s.push_str(&format!(
                    "  {} ch, {:?}, {}-{} Hz\n",
                    c.channels(),
                    c.sample_format(),
                    c.min_sample_rate().0,
                    c.max_sample_rate().0
                ));
            }
        }
        Err(e) => s.push_str(&format!("  unavailable: {e}\n")),
    }
    Ok(s)
}
pub fn start(device: Device, cfg: &Config, bypass: bool) -> Result<LiveStreams> {
    cfg.validate().map_err(anyhow::Error::msg)?;
    let in_supported=device.supported_input_configs().context("querying selected device input configurations")?.filter(|c|c.channels() as usize>=INPUT_CHANNELS&&c.sample_format()==SampleFormat::F32&&c.min_sample_rate().0<=SAMPLE_RATE&&c.max_sample_rate().0>=SAMPLE_RATE).max_by_key(|c|c.channels()).ok_or_else(||anyhow!("selected device has no f32 input configuration with at least 8 channels at 48000 Hz"))?;
    let out_supported=device.supported_output_configs().context("querying selected device output configurations")?.filter(|c|c.channels() as usize>=OUTPUT_CHANNELS&&c.sample_format()==SampleFormat::F32&&c.min_sample_rate().0<=SAMPLE_RATE&&c.max_sample_rate().0>=SAMPLE_RATE).max_by_key(|c|c.channels()).ok_or_else(||anyhow!("selected device has no f32 output configuration with at least 2 channels at 48000 Hz"))?;
    validate_channel_availability(cfg, in_supported.channels(), out_supported.channels())
        .map_err(anyhow::Error::msg)?;
    let in_channels = in_supported.channels();
    let out_channels = out_supported.channels();
    let mut in_config = in_supported
        .with_sample_rate(cpal::SampleRate(SAMPLE_RATE))
        .config();
    let mut out_config = out_supported
        .with_sample_rate(cpal::SampleRate(SAMPLE_RATE))
        .config();
    in_config.buffer_size = cpal::BufferSize::Fixed(cfg.buffer_frames);
    out_config.buffer_size = cpal::BufferSize::Fixed(cfg.buffer_frames);
    let cap = (cfg.buffer_frames as usize * 4).max(256);
    let (mut producer, mut consumer) = RingBuffer::<[f32; 8]>::new(cap);
    let meters = Arc::new(SharedMeters::default());
    let diagnostics = Arc::new(Diagnostics::default());
    let input_map = cfg.input_channels.map(|c| c as usize - 1);
    let overflow = Arc::clone(&diagnostics);
    let input_discont = Arc::clone(&diagnostics);
    let in_requested = cfg.buffer_frames as u64;
    let last_cb = Arc::new(AtomicU64::new(0));
    let last_in = Arc::clone(&last_cb);
    let input = device
        .build_input_stream(
            &in_config,
            move |data: &[f32], _| {
                let frames = data.len() / in_channels as usize;
                overflow
                    .input_callback_min_frames
                    .fetch_min(frames as u64, Ordering::Relaxed);
                overflow
                    .input_callback_max_frames
                    .fetch_max(frames as u64, Ordering::Relaxed);
                for f in 0..frames {
                    let mut frame = [0.0f32; 8];
                    for c in 0..8 {
                        frame[c] = data[f * in_channels as usize + input_map[c]];
                    }
                    if producer.push(frame).is_err() {
                        overflow.input_overflow.fetch_add(1, Ordering::Relaxed);
                    }
                }
                let n = last_in.fetch_add(frames as u64, Ordering::Relaxed);
                if n > 0 && frames as u64 != in_requested {
                    input_discont
                        .input_discontinuities
                        .fetch_add(1, Ordering::Relaxed);
                }
            },
            move |_| {},
            None,
        )
        .context("building CPAL input stream")?;
    // Callback-owned buffers are allocated before the stream starts. Processing is
    // performed in output callback chunks; no callback path allocates or locks.
    let max_frames = 2048usize;
    let mut in_scratch = vec![0.0f32; max_frames * 8];
    let mut out_scratch = vec![0.0f32; max_frames * 2];
    let mut processor = Processor::new(max_frames);
    processor
        .set_role_trims(cfg.role_trims)
        .map_err(anyhow::Error::msg)?;
    processor
        .set_master_trim(cfg.master_trim)
        .map_err(anyhow::Error::msg)?;
    processor.set_bypass(bypass);
    processor.attach_meters(Arc::clone(&meters));
    let out_map = cfg.output_channels.map(|c| c as usize - 1);
    let underflow = Arc::clone(&diagnostics);
    let dspdur = Arc::clone(&diagnostics);
    let outdis = Arc::clone(&diagnostics);
    let out_last = Arc::new(AtomicU64::new(0));
    let out_last_cb = Arc::clone(&out_last);
    let requested = cfg.buffer_frames as u64;
    let output = device
        .build_output_stream(
            &out_config,
            move |data: &mut [f32], _| {
                let frames = data.len() / out_channels as usize;
                underflow
                    .output_callback_min_frames
                    .fetch_min(frames as u64, Ordering::Relaxed);
                underflow
                    .output_callback_max_frames
                    .fetch_max(frames as u64, Ordering::Relaxed);
                let mut offset = 0;
                while offset < frames {
                    let n = (frames - offset).min(max_frames);
                    for f in 0..n {
                        if let Ok(frame) = consumer.pop() {
                            in_scratch[f * 8..f * 8 + 8].copy_from_slice(&frame);
                        } else {
                            in_scratch[f * 8..f * 8 + 8].fill(0.0);
                            underflow.output_underflow.fetch_add(1, Ordering::Relaxed);
                        }
                    }
                    let t = Instant::now();
                    let _ =
                        processor.process_block(&in_scratch[..n * 8], &mut out_scratch[..n * 2]);
                    let ns = t.elapsed().as_nanos().min(u64::MAX as u128) as u64;
                    dspdur.largest_dsp_ns.fetch_max(ns, Ordering::Relaxed);
                    for f in 0..n {
                        for c in 0..out_channels as usize {
                            data[(offset + f) * out_channels as usize + c] = 0.0;
                        }
                        for c in 0..2 {
                            data[(offset + f) * out_channels as usize + out_map[c]] =
                                out_scratch[f * 2 + c];
                        }
                    }
                    offset += n;
                }
                let n = out_last_cb.fetch_add(frames as u64, Ordering::Relaxed);
                if n > 0 && frames as u64 != requested {
                    outdis
                        .output_discontinuities
                        .fetch_add(1, Ordering::Relaxed);
                }
            },
            move |_| {},
            None,
        )
        .context("building CPAL output stream")?;
    input.play()?;
    output.play()?;
    Ok(LiveStreams {
        _input: input,
        _output: output,
        meters,
        diagnostics,
        input_config: in_config,
        output_config: out_config,
        buffering_frames: cap,
    })
}

pub fn validate_channel_availability(
    cfg: &Config,
    input_count: u16,
    output_count: u16,
) -> Result<(), String> {
    if cfg.input_channels.iter().any(|c| *c > input_count) {
        return Err(format!(
            "selected input channel exceeds device input channel count {input_count}"
        ));
    }
    if cfg.output_channels.iter().any(|c| *c > output_count) {
        return Err(format!(
            "selected output channel exceeds device output channel count {output_count}"
        ));
    }
    Ok(())
}
pub fn select_device(selector: &str) -> Result<Device> {
    let ds = list_devices()?;
    if let Ok(n) = selector.parse::<usize>() {
        return ds
            .get(n)
            .map(|x| x.1.clone())
            .ok_or_else(|| anyhow!("device index {n} does not exist"));
    }
    let matches: Vec<_> = ds.iter().filter(|x| x.0 == selector).collect();
    if matches.len() != 1 {
        return Err(anyhow!(
            "device name must match exactly one enumerated device; found {} matches",
            matches.len()
        ));
    }
    Ok(matches[0].1.clone())
}
#[allow(dead_code)]
fn _ensure_types(_: Producer<[f32; 8]>, _: Consumer<[f32; 8]>) {}
