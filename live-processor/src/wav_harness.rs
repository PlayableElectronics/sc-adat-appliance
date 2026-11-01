use crate::{config::Config, core::Processor, INPUT_CHANNELS, OUTPUT_CHANNELS, SAMPLE_RATE};
use anyhow::{anyhow, Context, Result};
use hound::{WavReader, WavSpec, WavWriter};
use std::path::Path;

pub fn process_files(
    inputs: [&Path; 8],
    output: &Path,
    block_size: usize,
    cfg: &Config,
) -> Result<()> {
    cfg.validate().map_err(anyhow::Error::msg)?;
    if block_size == 0 {
        return Err(anyhow!("block size must be positive"));
    }
    let mut readers: Vec<WavReader<std::io::BufReader<std::fs::File>>> = inputs
        .iter()
        .map(|p| WavReader::open(p).with_context(|| format!("opening {}", p.display())))
        .collect::<Result<_>>()?;
    let first = readers[0].spec();
    if first.channels != 1 || first.sample_rate != SAMPLE_RATE {
        return Err(anyhow!(
            "all input files must be mono at {SAMPLE_RATE} Hz; {} is {} ch at {} Hz",
            inputs[0].display(),
            first.channels,
            first.sample_rate
        ));
    }
    let len = readers[0].duration();
    for (i, r) in readers.iter().enumerate() {
        let s = r.spec();
        if s.channels != 1 || s.sample_rate != SAMPLE_RATE || r.duration() != len {
            return Err(anyhow!(
                "input {} ({}) does not match mono/48000 Hz/{} samples",
                i + 1,
                inputs[i].display(),
                len
            ));
        }
    }
    let spec = WavSpec {
        channels: 2,
        sample_rate: SAMPLE_RATE,
        bits_per_sample: 32,
        sample_format: hound::SampleFormat::Float,
    };
    let mut writer = WavWriter::create(output, spec)?;
    let mut p = Processor::new(block_size);
    p.set_role_trims(cfg.role_trims)
        .map_err(anyhow::Error::msg)?;
    p.set_master_trim(cfg.master_trim)
        .map_err(anyhow::Error::msg)?;
    if readers.iter().any(|r| {
        r.spec().sample_format == hound::SampleFormat::Int && r.spec().bits_per_sample > 32
    }) {
        return Err(anyhow!(
            "integer WAV inputs wider than 32 bits are unsupported"
        ));
    }
    let mut scratch = vec![0.0f32; block_size * INPUT_CHANNELS];
    let mut out = vec![0.0f32; block_size * OUTPUT_CHANNELS];
    let mut pos = 0u64;
    while pos < len as u64 {
        let n = (len as u64 - pos).min(block_size as u64) as usize;
        for f in 0..n {
            for ch in 0..INPUT_CHANNELS {
                scratch[f * 8 + ch] = read_normalized(&mut readers[ch])?
                    .ok_or_else(|| anyhow!("short read in input {}", ch + 1))?;
            }
        }
        p.process_block(&scratch[..n * 8], &mut out[..n * 2])
            .map_err(anyhow::Error::msg)?;
        for x in &out[..n * 2] {
            writer.write_sample(*x)?;
        }
        pos += n as u64;
    }
    writer.finalize()?;
    let m = p.meters();
    println!(
        "Processed {len} frames at {SAMPLE_RATE} Hz in blocks up to {block_size} frames; wrote {}",
        output.display()
    );
    for (i, r) in m.roles.iter().enumerate() {
        let file_headroom = if r.peak_hold > 0.0 {
            -20.0 * r.peak_hold.log10()
        } else {
            f32::INFINITY
        };
        let file_crest = if r.rms > 1e-20 {
            r.peak_hold / r.rms
        } else {
            0.0
        };
        println!("{} final_block_peak={:.6} file_peak_hold={:.6} short_rms={:.6} file_peak_to_short_rms_crest={:.3} file_peak_headroom={:.2} dBFS L/R final-block peak={:.6}/{:.6} balance={:.3} correlation={:.3} invalid={} over_in_file={}",crate::Role::ALL[i].name(),r.peak,r.peak_hold,r.rms,file_crest,file_headroom,r.left_peak,r.right_peak,r.balance,r.correlation,r.non_finite_samples,r.peak_hold>=1.0);
    }
    println!(
        "output peak L/R={:.6}/{:.6} RMS L/R={:.6}/{:.6} clipping_frames={} invalid={}",
        m.output.left_peak,
        m.output.right_peak,
        m.output.left_rms,
        m.output.right_rms,
        m.output.clipping,
        m.output.invalid
    );
    Ok(())
}

fn read_normalized(
    reader: &mut WavReader<std::io::BufReader<std::fs::File>>,
) -> Result<Option<f32>> {
    let spec = reader.spec();
    match spec.sample_format {
        hound::SampleFormat::Float => Ok(reader.samples::<f32>().next().transpose()?),
        hound::SampleFormat::Int => Ok(reader
            .samples::<i32>()
            .next()
            .transpose()?
            .map(|x| (x as f64 / 2.0f64.powi(spec.bits_per_sample as i32 - 1)) as f32)),
    }
}
