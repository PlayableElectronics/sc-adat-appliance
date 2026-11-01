use adat_live_processor::{config::Config, live, wav_harness};
use anyhow::{anyhow, Result};
use clap::{Parser, Subcommand};
use cpal::traits::DeviceTrait;
use std::{path::PathBuf, thread, time::Duration};

#[derive(Parser)]
#[command(
    name = "adat-live-processor",
    about = "Role-aware live 8-in/2-out summing engine"
)]
struct Args {
    #[command(subcommand)]
    command: Command,
}
#[derive(Subcommand)]
enum Command {
    ListDevices,
    InspectDevice {
        device: String,
    },
    Run {
        #[arg(long)]
        device: String,
        #[arg(long)]
        buffer: Option<u32>,
        #[arg(long, value_delimiter = ',')]
        inputs: Option<Vec<u16>>,
        #[arg(long, value_delimiter = ',')]
        outputs: Option<Vec<u16>>,
        #[arg(long)]
        master_trim: Option<f32>,
        #[arg(long)]
        bypass: bool,
        #[arg(long)]
        config: Option<PathBuf>,
        #[arg(long, default_value = "2")]
        report_seconds: u64,
    },
    ProcessWav {
        #[arg(required = true, num_args = 8)]
        inputs: Vec<PathBuf>,
        #[arg(long)]
        output: PathBuf,
        #[arg(long, default_value = "128")]
        block: usize,
        #[arg(long)]
        config: Option<PathBuf>,
    },
    ValidateConfig {
        #[arg(long)]
        config: PathBuf,
    },
}
fn main() -> Result<()> {
    let args = Args::parse();
    match args.command {
        Command::ListDevices => {
            println!("Default CPAL host: {:?}", cpal::default_host().id());
            for (i, (n, d)) in live::list_devices()?.iter().enumerate() {
                println!("{i}: {n}");
                println!("{}", live::inspect_device(d)?);
            }
        }
        Command::InspectDevice { device } => {
            println!("{}", live::inspect_device(&live::select_device(&device)?)?)
        }
        Command::ValidateConfig { config } => {
            Config::load(config).map_err(anyhow::Error::msg)?;
            println!("configuration valid");
        }
        Command::ProcessWav {
            inputs,
            output,
            block,
            config,
        } => {
            let c = if let Some(p) = config {
                Config::load(p).map_err(anyhow::Error::msg)?
            } else {
                Config::default()
            };
            let a: [&std::path::Path; 8] = inputs
                .iter()
                .map(PathBuf::as_path)
                .collect::<Vec<_>>()
                .try_into()
                .map_err(|_| anyhow!("exactly eight input WAVs are required"))?;
            wav_harness::process_files(a, &output, block, &c)?;
        }
        Command::Run {
            device,
            buffer,
            inputs,
            outputs,
            master_trim,
            bypass,
            config,
            report_seconds,
        } => {
            let mut c = if let Some(p) = config {
                Config::load(p).map_err(anyhow::Error::msg)?
            } else {
                Config::default()
            };
            if let Some(inputs) = inputs {
                c.input_channels = inputs
                    .try_into()
                    .map_err(|_| anyhow!("exactly eight input channels are required"))?;
            }
            if let Some(outputs) = outputs {
                c.output_channels = outputs
                    .try_into()
                    .map_err(|_| anyhow!("exactly two output channels are required"))?;
            }
            if let Some(buffer) = buffer {
                c.buffer_frames = buffer;
            }
            if let Some(master_trim) = master_trim {
                c.master_trim = master_trim;
            }
            c.validate().map_err(anyhow::Error::msg)?;
            let d = live::select_device(&device)?;
            println!("Selected device: {}", d.name()?);
            let streams = live::start(d, &c, bypass)?;
            println!("Running 48 kHz; physical input channels {:?}; output channels {:?}; requested {} frames; CPAL configs input={:?} output={:?}; ring capacity {} frames (maximum queued duration {:.2} ms)",c.input_channels,c.output_channels,c.buffer_frames,streams.input_config,streams.output_config,streams.buffering_frames,streams.buffering_frames as f64/48.0);
            loop {
                thread::sleep(Duration::from_secs(report_seconds.max(1)));
                let m = streams.meters.snapshot();
                let d = &streams.diagnostics;
                let in_min = d
                    .input_callback_min_frames
                    .load(std::sync::atomic::Ordering::Relaxed);
                let out_min = d
                    .output_callback_min_frames
                    .load(std::sync::atomic::Ordering::Relaxed);
                println!(
                    "callback frames input={}-{} output={}-{}",
                    if in_min == u64::MAX { 0 } else { in_min },
                    d.input_callback_max_frames
                        .load(std::sync::atomic::Ordering::Relaxed),
                    if out_min == u64::MAX { 0 } else { out_min },
                    d.output_callback_max_frames
                        .load(std::sync::atomic::Ordering::Relaxed)
                );
                println!("DSP max={} us input_overflow_frames={} output_underflow_frames={} input_discontinuity={} output_discontinuity={} output_peak L/R={:.4}/{:.4} RMS L/R={:.4}/{:.4} clipping_frames={} invalid={}",d.largest_dsp_ns.load(std::sync::atomic::Ordering::Relaxed)/1000,d.input_overflow.load(std::sync::atomic::Ordering::Relaxed),d.output_underflow.load(std::sync::atomic::Ordering::Relaxed),d.input_discontinuities.load(std::sync::atomic::Ordering::Relaxed),d.output_discontinuities.load(std::sync::atomic::Ordering::Relaxed),m.output.left_peak,m.output.right_peak,m.output.left_rms,m.output.right_rms,m.output.clipping,m.output.invalid);
                for (i, r) in m.roles.iter().enumerate() {
                    println!("  {} peak={:.4} hold={:.4} rms={:.4} crest={:.2} headroom={:.2} dBFS balance={:.3} corr={:.3} invalid={} over={}",adat_live_processor::Role::ALL[i].name(),r.peak,r.peak_hold,r.rms,r.crest_factor,r.headroom_db,r.balance,r.correlation,r.non_finite_samples,r.over);
                }
            }
        }
    }
    Ok(())
}
