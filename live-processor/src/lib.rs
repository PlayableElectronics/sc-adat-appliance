pub mod config;
pub mod core;
pub mod live;
pub mod wav_harness;

pub const SAMPLE_RATE: u32 = 48_000;
pub const INPUT_CHANNELS: usize = 8;
pub const OUTPUT_CHANNELS: usize = 2;
pub const ROLE_COUNT: usize = 5;
pub const RMS_TIME_CONSTANT_SECONDS: f32 = 0.300;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
#[repr(usize)]
pub enum Role {
    Kick = 0,
    Bass = 1,
    Drums = 2,
    SynthsMusic = 3,
    VocalLoopsFx = 4,
}

impl Role {
    pub const ALL: [Role; ROLE_COUNT] = [
        Role::Kick,
        Role::Bass,
        Role::Drums,
        Role::SynthsMusic,
        Role::VocalLoopsFx,
    ];
    pub const fn name(self) -> &'static str {
        match self {
            Self::Kick => "kick",
            Self::Bass => "bass",
            Self::Drums => "drums",
            Self::SynthsMusic => "synths_music",
            Self::VocalLoopsFx => "vocal_loops_fx",
        }
    }
    pub const fn channels(self) -> &'static [usize] {
        match self {
            Self::Kick => &[0],
            Self::Bass => &[1],
            Self::Drums => &[2, 3],
            Self::SynthsMusic => &[4, 5],
            Self::VocalLoopsFx => &[6, 7],
        }
    }
    pub const fn is_stereo(self) -> bool {
        !matches!(self, Self::Kick | Self::Bass)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::{config::Config, core::Processor, wav_harness};
    fn run(x: &[f32], n: usize) -> Vec<f32> {
        let mut p = Processor::new(n);
        let mut y = vec![0.0; x.len() / 4];
        let mut offset = 0;
        for s in x.chunks(n * 8) {
            let frames = s.len() / 8;
            p.process_block(s, &mut y[offset..offset + frames * 2])
                .unwrap();
            offset += frames * 2;
        }
        y
    }
    #[test]
    fn fixed_role_mapping_and_unity_sum() {
        let mut x = [0.0; 8];
        x[0] = 0.2;
        x[1] = 0.3;
        x[2] = 0.4;
        x[3] = 0.5;
        x[4] = 0.6;
        x[5] = 0.7;
        x[6] = 0.8;
        x[7] = 0.9;
        let mut y = [0.0; 2];
        Processor::new(1).process_block(&x, &mut y).unwrap();
        let k = std::f32::consts::FRAC_1_SQRT_2;
        assert!((y[0] - (0.2 * k + 0.3 * k + 0.4 + 0.6 + 0.8)).abs() < 1e-6);
        assert!((y[1] - (0.2 * k + 0.3 * k + 0.5 + 0.7 + 0.9)).abs() < 1e-6);
        assert_eq!(
            Role::ALL.map(Role::channels),
            [&[0][..], &[1][..], &[2, 3][..], &[4, 5][..], &[6, 7][..]]
        );
    }
    #[test]
    fn mono_centre_constant_power_and_stereo_orientation() {
        let mut p = Processor::new(2);
        let mut y = [0.0; 4];
        p.process_block(
            &[
                1., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0., 0.,
            ],
            &mut y,
        )
        .unwrap();
        assert!((y[0] - std::f32::consts::FRAC_1_SQRT_2).abs() < 1e-6);
        assert_eq!(y[0], y[1]);
        let mut x = [0.; 8];
        x[2] = 1.;
        let mut z = [0.; 2];
        Processor::new(1).process_block(&x, &mut z).unwrap();
        assert!(z[0] > z[1]);
    }
    #[test]
    fn trims_bypass_and_no_reversal() {
        let mut p = Processor::new(1);
        p.set_role_trims([2., 1., 1., 1., 1.]).unwrap();
        p.set_master_trim(0.5).unwrap();
        let mut y = [0.; 2];
        p.process_block(&[1., 0., 0., 0., 0., 0., 0., 0.], &mut y)
            .unwrap();
        assert!((y[0] - std::f32::consts::FRAC_1_SQRT_2).abs() < 1e-6);
        let mut p = Processor::new(1);
        p.set_role_trims([0.; 5]).unwrap();
        p.set_master_trim(0.).unwrap();
        p.set_bypass(true);
        let mut z = [0.; 2];
        p.process_block(&[1., 1., 0., 0., 0., 0., 0., 0.], &mut z)
            .unwrap();
        assert_eq!(z, [2., 2.]);
        let mut p = Processor::new(1);
        let mut a = [0.; 2];
        p.process_block(&[0., 0., 0., 0., 1., 0., 0., 0.], &mut a)
            .unwrap();
        assert!(a[0] > a[1]);
    }
    #[test]
    fn size_independent_reset_is_deterministic() {
        let x = vec![0.25; 8 * 137];
        let y1 = run(&x, 1);
        let y64 = run(&x, 64);
        assert!(y1.iter().zip(y64).all(|(a, b)| (a - b).abs() < 1e-6));
        let mut p = Processor::new(128);
        let mut a = vec![0.; 256];
        p.process_block(&x[..1024], &mut a[..256]).unwrap();
        p.reset();
        let mut b = vec![0.; 256];
        p.process_block(&x[..1024], &mut b[..256]).unwrap();
        assert_eq!(a, b);
    }
    #[test]
    fn meter_math_stereo_and_peak_hold() {
        let mut p = Processor::new(4);
        let mut y = [0.; 4];
        p.process_block(
            &[
                0., 0., 1., 0., 0., 0., 0., 0., 0., 0., 0.5, 0.5, 0., 0., 0., 0.,
            ],
            &mut y,
        )
        .unwrap();
        let m = p.meters();
        let d = m.roles[Role::Drums as usize];
        assert_eq!(d.peak_hold, 1.0);
        assert_eq!(d.peak, 1.0);
        assert!(d.rms > 0.0);
        let alpha = (-1.0f64 / (SAMPLE_RATE as f64 * RMS_TIME_CONSTANT_SECONDS as f64)).exp();
        let expected_rms_sq = (1.0 - alpha) * 0.5 * alpha + (1.0 - alpha) * 0.25;
        assert!((d.rms as f64 * d.rms as f64 - expected_rms_sq).abs() < 1e-9);
        assert!((d.crest_factor - d.peak / d.rms).abs() < 1e-6);
        assert!((d.balance + 1.0 / 3.0).abs() < 1e-6);
        assert!(d.correlation > 0.0 && d.correlation < 1.0);
        assert_eq!(m.output.left_peak, 1.0);
        assert_eq!(m.output.right_peak, 0.5);
        assert!(m.output.left_rms > m.output.right_rms);
        assert!(m.roles[Role::Kick as usize].headroom_db.is_infinite());
    }
    #[test]
    fn non_finite_inputs_and_overflow_outputs_are_contained() {
        let mut p = Processor::new(2);
        let mut y = [0.; 4];
        p.process_block(
            &[
                f32::NAN,
                0.,
                0.,
                0.,
                0.,
                0.,
                0.,
                0.,
                f32::INFINITY,
                0.,
                0.,
                0.,
                0.,
                0.,
                0.,
                0.,
            ],
            &mut y,
        )
        .unwrap();
        assert!(y.iter().all(|x| x.is_finite()));
        assert_eq!(p.meters().roles[0].non_finite_samples, 2);
        let mut p = Processor::new(1);
        let mut z = [0.; 2];
        p.set_role_trims([f32::MAX, 1., 1., 1., 1.]).unwrap();
        p.process_block(&[f32::MAX, 0., 0., 0., 0., 0., 0., 0.], &mut z)
            .unwrap();
        assert!(z.iter().all(|x| x.is_finite()));
        assert_eq!(p.meters().output.invalid, 2);
    }
    #[test]
    fn validates_buffers_and_configuration() {
        let mut p = Processor::new(4);
        assert!(p.process_block(&[0.; 7], &mut []).is_err());
        assert!(p.process_block(&[0.; 40], &mut [0.; 10]).is_err());
        assert!(Processor::with_rate(44100, 64).is_err());
        assert!(Config {
            sample_rate: 44100,
            ..Config::default()
        }
        .validate()
        .is_err());
        assert!(Config {
            input_channels: [1, 1, 3, 4, 5, 6, 7, 8],
            ..Config::default()
        }
        .validate()
        .is_err());
        assert!(Config {
            output_channels: [1, 4],
            ..Config::default()
        }
        .validate()
        .is_ok());
        assert!(live::validate_channel_availability(&Config::default(), 8, 2).is_ok());
        assert!(live::validate_channel_availability(
            &Config {
                input_channels: [3, 4, 5, 6, 7, 8, 9, 10],
                ..Config::default()
            },
            8,
            2
        )
        .is_err());
        assert!(live::validate_channel_availability(
            &Config {
                output_channels: [1, 3],
                ..Config::default()
            },
            8,
            2
        )
        .is_err());
        assert!(Config {
            version: 2,
            ..Config::default()
        }
        .validate()
        .is_err());
    }
    #[test]
    fn atomic_snapshots_track_core() {
        let mut p = Processor::new(1);
        let shared = std::sync::Arc::new(core::SharedMeters::default());
        p.attach_meters(shared.clone());
        let mut y = [0.; 2];
        p.process_block(&[0.5, 0., 0., 0., 0., 0., 0., 0.], &mut y)
            .unwrap();
        assert_eq!(shared.snapshot().roles[0].peak, 0.5);
    }
    #[test]
    fn wav_harness_uses_core_and_rejects_mismatch() {
        let d = tempfile::tempdir().unwrap();
        let paths: Vec<_> = (0..8)
            .map(|i| {
                let path = d.path().join(format!("{i}.wav"));
                let mut w = hound::WavWriter::create(
                    &path,
                    hound::WavSpec {
                        channels: 1,
                        sample_rate: SAMPLE_RATE,
                        bits_per_sample: 32,
                        sample_format: hound::SampleFormat::Float,
                    },
                )
                .unwrap();
                for _ in 0..16 {
                    w.write_sample(if i == 0 { 0.25f32 } else { 0.0 }).unwrap();
                }
                w.finalize().unwrap();
                path
            })
            .collect();
        let refs: [&std::path::Path; 8] = paths
            .iter()
            .map(|p| p.as_path())
            .collect::<Vec<_>>()
            .try_into()
            .unwrap();
        let out = d.path().join("out.wav");
        wav_harness::process_files(refs, &out, 3, &Config::default()).unwrap();
        let out_alt = d.path().join("out-alt.wav");
        wav_harness::process_files(refs, &out_alt, 7, &Config::default()).unwrap();
        let r = hound::WavReader::open(&out).unwrap();
        let samples: Vec<f32> = r.into_samples().map(Result::unwrap).collect();
        let r_alt = hound::WavReader::open(&out_alt).unwrap();
        let samples_alt: Vec<f32> = r_alt.into_samples().map(Result::unwrap).collect();
        assert_eq!(samples.len(), 32);
        assert!(samples
            .iter()
            .zip(samples_alt)
            .all(|(a, b)| (a - b).abs() < 1e-6));
        assert!((samples[0] - 0.25 * std::f32::consts::FRAC_1_SQRT_2).abs() < 1e-6);
        let bad = d.path().join("bad.wav");
        let mut w = hound::WavWriter::create(
            &bad,
            hound::WavSpec {
                channels: 1,
                sample_rate: 44100,
                bits_per_sample: 16,
                sample_format: hound::SampleFormat::Int,
            },
        )
        .unwrap();
        w.write_sample(0i16).unwrap();
        w.finalize().unwrap();
        let mut badrefs = refs;
        badrefs[7] = bad.as_path();
        assert!(wav_harness::process_files(badrefs, &out, 3, &Config::default()).is_err());
        let short = d.path().join("short.wav");
        let mut w = hound::WavWriter::create(
            &short,
            hound::WavSpec {
                channels: 1,
                sample_rate: SAMPLE_RATE,
                bits_per_sample: 32,
                sample_format: hound::SampleFormat::Float,
            },
        )
        .unwrap();
        for _ in 0..15 {
            w.write_sample(0.0f32).unwrap();
        }
        w.finalize().unwrap();
        badrefs[7] = short.as_path();
        assert!(wav_harness::process_files(badrefs, &out, 3, &Config::default()).is_err());
    }
}
