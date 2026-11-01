use crate::{
    Role, INPUT_CHANNELS, OUTPUT_CHANNELS, RMS_TIME_CONSTANT_SECONDS, ROLE_COUNT, SAMPLE_RATE,
};
use std::sync::atomic::{AtomicU32, AtomicU64, Ordering};

#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct RoleMeter {
    pub peak: f32,
    pub peak_hold: f32,
    pub rms: f32,
    pub crest_factor: f32,
    pub headroom_db: f32,
    pub non_finite_samples: u64,
    pub over: bool,
    pub left_peak: f32,
    pub right_peak: f32,
    pub balance: f32,
    pub correlation: f32,
}
#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct OutputMeter {
    pub left_peak: f32,
    pub right_peak: f32,
    pub left_rms: f32,
    pub right_rms: f32,
    pub clipping: u64,
    pub invalid: u64,
}
#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct MeterSnapshot {
    pub roles: [RoleMeter; ROLE_COUNT],
    pub output: OutputMeter,
}

struct RoleState {
    peak_hold: f32,
    rms_sq: f64,
    ll: f64,
    rr: f64,
    lr: f64,
    invalid: u64,
}
impl Default for RoleState {
    fn default() -> Self {
        Self {
            peak_hold: 0.0,
            rms_sq: 0.0,
            ll: 0.0,
            rr: 0.0,
            lr: 0.0,
            invalid: 0,
        }
    }
}
struct OutputState {
    l_sq: f64,
    r_sq: f64,
    left_peak: f32,
    right_peak: f32,
    clipping: u64,
    invalid: u64,
}
impl Default for OutputState {
    fn default() -> Self {
        Self {
            l_sq: 0.0,
            r_sq: 0.0,
            left_peak: 0.0,
            right_peak: 0.0,
            clipping: 0,
            invalid: 0,
        }
    }
}

/// Atomic, lock-free meter publication. Readers can observe adjacent fields from
/// slightly different callbacks; every individual value is race-free.
pub struct SharedMeters {
    values: [AtomicU32; ROLE_COUNT * 11 + 6],
    counters: [AtomicU64; ROLE_COUNT + 2],
}
impl Default for SharedMeters {
    fn default() -> Self {
        Self {
            values: std::array::from_fn(|_| AtomicU32::new(0)),
            counters: std::array::from_fn(|_| AtomicU64::new(0)),
        }
    }
}
impl SharedMeters {
    fn publish(&self, m: MeterSnapshot) {
        for (i, role) in m.roles.iter().enumerate() {
            let vals = [
                role.peak,
                role.peak_hold,
                role.rms,
                role.crest_factor,
                role.headroom_db,
                role.over as u8 as f32,
                role.left_peak,
                role.right_peak,
                role.balance,
                role.correlation,
                0.0,
            ];
            for (j, v) in vals.into_iter().enumerate() {
                self.values[i * 11 + j].store(v.to_bits(), Ordering::Relaxed);
            }
            self.counters[i].store(role.non_finite_samples, Ordering::Relaxed);
        }
        let o = ROLE_COUNT * 11;
        for (j, v) in [
            m.output.left_peak,
            m.output.right_peak,
            m.output.left_rms,
            m.output.right_rms,
            0.0,
            0.0,
        ]
        .into_iter()
        .enumerate()
        {
            self.values[o + j].store(v.to_bits(), Ordering::Relaxed);
        }
        self.counters[ROLE_COUNT].store(m.output.clipping, Ordering::Relaxed);
        self.counters[ROLE_COUNT + 1].store(m.output.invalid, Ordering::Relaxed);
    }
    pub fn snapshot(&self) -> MeterSnapshot {
        let v = |i: usize| f32::from_bits(self.values[i].load(Ordering::Relaxed));
        let roles = std::array::from_fn(|i| RoleMeter {
            peak: v(i * 11),
            peak_hold: v(i * 11 + 1),
            rms: v(i * 11 + 2),
            crest_factor: v(i * 11 + 3),
            headroom_db: v(i * 11 + 4),
            over: v(i * 11 + 5) >= 1.0,
            left_peak: v(i * 11 + 6),
            right_peak: v(i * 11 + 7),
            balance: v(i * 11 + 8),
            correlation: v(i * 11 + 9),
            non_finite_samples: self.counters[i].load(Ordering::Relaxed),
        });
        let o = ROLE_COUNT * 11;
        MeterSnapshot {
            roles,
            output: OutputMeter {
                left_peak: v(o),
                right_peak: v(o + 1),
                left_rms: v(o + 2),
                right_rms: v(o + 3),
                clipping: self.counters[ROLE_COUNT].load(Ordering::Relaxed),
                invalid: self.counters[ROLE_COUNT + 1].load(Ordering::Relaxed),
            },
        }
    }
}

/// Transparent 8-to-2 summing core. Input is frame-interleaved: 8 f32 per frame;
/// output is frame-interleaved stereo. Centre mono uses equal-power 1/sqrt(2)
/// gain per side, so each source contributes unity power to the stereo pair.
/// Bypass routes kick and bass at unity to both outputs and stereo pairs directly,
/// ignoring every trim. Ordinary processing applies role trims then master trim.
pub struct Processor {
    sample_rate: u32,
    max_block: usize,
    trims: [f32; ROLE_COUNT],
    master: f32,
    bypass: bool,
    state: [RoleState; ROLE_COUNT],
    output: OutputState,
    shared: Option<std::sync::Arc<SharedMeters>>,
    last_peaks: [f32; ROLE_COUNT],
    last_left_peaks: [f32; ROLE_COUNT],
    last_right_peaks: [f32; ROLE_COUNT],
}
impl Processor {
    pub fn new(max_block: usize) -> Self {
        Self::with_rate(SAMPLE_RATE, max_block).expect("valid fixed sample rate")
    }
    pub fn with_rate(sample_rate: u32, max_block: usize) -> Result<Self, String> {
        if sample_rate != SAMPLE_RATE {
            return Err(format!("only {SAMPLE_RATE} Hz is supported"));
        }
        if max_block == 0 {
            return Err("maximum block length must be positive".into());
        }
        Ok(Self {
            sample_rate,
            max_block,
            trims: [1.0; ROLE_COUNT],
            master: 1.0,
            bypass: false,
            state: std::array::from_fn(|_| RoleState::default()),
            output: OutputState::default(),
            shared: None,
            last_peaks: [0.0; ROLE_COUNT],
            last_left_peaks: [0.0; ROLE_COUNT],
            last_right_peaks: [0.0; ROLE_COUNT],
        })
    }
    pub fn attach_meters(&mut self, meters: std::sync::Arc<SharedMeters>) {
        self.shared = Some(meters);
    }
    pub fn set_role_trims(&mut self, trims: [f32; ROLE_COUNT]) -> Result<(), String> {
        if trims.iter().any(|x| !x.is_finite() || *x < 0.0) {
            return Err("role trims must be finite and non-negative".into());
        }
        self.trims = trims;
        Ok(())
    }
    pub fn set_master_trim(&mut self, trim: f32) -> Result<(), String> {
        if !trim.is_finite() || trim < 0.0 {
            return Err("master trim must be finite and non-negative".into());
        }
        self.master = trim;
        Ok(())
    }
    pub fn set_bypass(&mut self, bypass: bool) {
        self.bypass = bypass
    }
    pub fn process_block(&mut self, input: &[f32], output: &mut [f32]) -> Result<(), &'static str> {
        if input.len() % INPUT_CHANNELS != 0 {
            return Err("input length must be a multiple of 8 channels");
        }
        let frames = input.len() / INPUT_CHANNELS;
        if frames > self.max_block {
            return Err("block exceeds configured maximum");
        }
        if output.len() != frames * OUTPUT_CHANNELS {
            return Err("output length must be exactly two samples per input frame");
        }
        let alpha = (-1.0 / (self.sample_rate as f64 * RMS_TIME_CONSTANT_SECONDS as f64)).exp();
        let mut peaks = [0.0f32; ROLE_COUNT];
        let mut lpeaks = [0.0f32; ROLE_COUNT];
        let mut rpeaks = [0.0f32; ROLE_COUNT];
        for frame in 0..frames {
            let src = &input[frame * INPUT_CHANNELS..(frame + 1) * INPUT_CHANNELS];
            let mut clean = [0.0f32; INPUT_CHANNELS];
            for (ch, s) in src.iter().enumerate() {
                if s.is_finite() {
                    clean[ch] = *s
                } else {
                    self.state[role_for_channel(ch)].invalid += 1;
                }
            }
            let mut l = 0.0f32;
            let mut r = 0.0f32;
            for role in Role::ALL {
                let i = role as usize;
                let ch = role.channels();
                let a = clean[ch[0]];
                let b = if ch.len() == 2 { clean[ch[1]] } else { a };
                let peak = a.abs().max(b.abs());
                peaks[i] = peaks[i].max(peak);
                lpeaks[i] = lpeaks[i].max(a.abs());
                rpeaks[i] = rpeaks[i].max(b.abs());
                let s = &mut self.state[i];
                s.peak_hold = s.peak_hold.max(peak);
                let energy = if ch.len() == 2 {
                    (a as f64 * a as f64 + b as f64 * b as f64) * 0.5
                } else {
                    a as f64 * a as f64
                };
                s.rms_sq = alpha * s.rms_sq + (1.0 - alpha) * energy;
                if ch.len() == 2 {
                    s.ll = alpha * s.ll + (1.0 - alpha) * a as f64 * a as f64;
                    s.rr = alpha * s.rr + (1.0 - alpha) * b as f64 * b as f64;
                    s.lr = alpha * s.lr + (1.0 - alpha) * a as f64 * b as f64;
                }
                if self.bypass {
                    if ch.len() == 1 {
                        l += a;
                        r += a
                    } else {
                        l += a;
                        r += b
                    }
                } else {
                    let gain = self.trims[i];
                    if ch.len() == 1 {
                        let g = std::f32::consts::FRAC_1_SQRT_2 * gain;
                        l += a * g;
                        r += a * g;
                    } else {
                        l += a * gain;
                        r += b * gain;
                    }
                }
            }
            if !self.bypass {
                l *= self.master;
                r *= self.master;
            }
            let oi = frame * 2;
            output[oi] = safe_output(l, &mut self.output);
            output[oi + 1] = safe_output(r, &mut self.output);
            self.output.left_peak = self.output.left_peak.max(output[oi].abs());
            self.output.right_peak = self.output.right_peak.max(output[oi + 1].abs());
            self.output.l_sq =
                alpha * self.output.l_sq + (1.0 - alpha) * output[oi] as f64 * output[oi] as f64;
            self.output.r_sq = alpha * self.output.r_sq
                + (1.0 - alpha) * output[oi + 1] as f64 * output[oi + 1] as f64;
            if output[oi].abs() > 1.0 || output[oi + 1].abs() > 1.0 {
                self.output.clipping += 1;
            }
        }
        self.last_peaks = peaks;
        self.last_left_peaks = lpeaks;
        self.last_right_peaks = rpeaks;
        let snap = self.snapshot_with(peaks, lpeaks, rpeaks);
        if let Some(m) = &self.shared {
            m.publish(snap)
        }
        Ok(())
    }
    fn snapshot_with(
        &self,
        peaks: [f32; ROLE_COUNT],
        lp: [f32; ROLE_COUNT],
        rp: [f32; ROLE_COUNT],
    ) -> MeterSnapshot {
        let roles = std::array::from_fn(|i| {
            let s = &self.state[i];
            let rms = (s.rms_sq.sqrt()) as f32;
            let (bal, corr) = if Role::ALL[i].is_stereo() {
                let denom = (s.ll * s.rr).sqrt();
                let c = if denom > 1e-20 {
                    (s.lr / denom).clamp(-1.0, 1.0) as f32
                } else {
                    0.0
                };
                let den = lp[i] + rp[i];
                (
                    if den > 0.0 {
                        (rp[i] - lp[i]) / den
                    } else {
                        0.0
                    },
                    c,
                )
            } else {
                (0.0, 0.0)
            };
            RoleMeter {
                peak: peaks[i],
                peak_hold: s.peak_hold,
                rms,
                crest_factor: if rms > 1e-20 { peaks[i] / rms } else { 0.0 },
                headroom_db: if peaks[i] > 0.0 {
                    -20.0 * peaks[i].log10()
                } else {
                    f32::INFINITY
                },
                non_finite_samples: s.invalid,
                over: peaks[i] >= 1.0,
                left_peak: lp[i],
                right_peak: rp[i],
                balance: bal,
                correlation: corr,
            }
        });
        MeterSnapshot {
            roles,
            output: OutputMeter {
                left_peak: self.output.left_peak,
                right_peak: self.output.right_peak,
                left_rms: (self.output.l_sq.sqrt()) as f32,
                right_rms: (self.output.r_sq.sqrt()) as f32,
                clipping: self.output.clipping,
                invalid: self.output.invalid,
            },
        }
    }
    pub fn meters(&self) -> MeterSnapshot {
        self.snapshot_with(self.last_peaks, self.last_left_peaks, self.last_right_peaks)
    }
    pub fn reset(&mut self) {
        self.state = std::array::from_fn(|_| RoleState::default());
        self.output = OutputState::default();
        self.last_peaks = [0.0; ROLE_COUNT];
        self.last_left_peaks = [0.0; ROLE_COUNT];
        self.last_right_peaks = [0.0; ROLE_COUNT];
        if let Some(m) = &self.shared {
            m.publish(MeterSnapshot::default())
        }
    }
}
fn role_for_channel(ch: usize) -> usize {
    match ch {
        0 => 0,
        1 => 1,
        2 | 3 => 2,
        4 | 5 => 3,
        _ => 4,
    }
}
fn safe_output(x: f32, state: &mut OutputState) -> f32 {
    if x.is_finite() {
        x
    } else {
        state.invalid += 1;
        0.0
    }
}
