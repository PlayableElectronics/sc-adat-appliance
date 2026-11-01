use crate::{Role, ROLE_COUNT, SAMPLE_RATE};
use serde::{Deserialize, Serialize};
use std::{fs, path::Path};

#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct Config {
    pub version: u32,
    pub sample_rate: u32,
    pub input_channels: [u16; 8],
    pub output_channels: [u16; 2],
    pub role_trims: [f32; ROLE_COUNT],
    pub master_trim: f32,
    pub buffer_frames: u32,
    pub meter_targets: [MeterTarget; ROLE_COUNT],
}
#[derive(Clone, Debug, Serialize, Deserialize)]
pub struct MeterTarget {
    pub role: String,
    pub low_dbfs: f32,
    pub good_dbfs: f32,
    pub hot_dbfs: f32,
}
impl Default for Config {
    fn default() -> Self {
        Self {
            version: 1,
            sample_rate: SAMPLE_RATE,
            input_channels: [1, 2, 3, 4, 5, 6, 7, 8],
            output_channels: [1, 2],
            role_trims: [1.0; ROLE_COUNT],
            master_trim: 1.0,
            buffer_frames: 128,
            meter_targets: Role::ALL.map(|r| MeterTarget {
                role: r.name().to_string(),
                low_dbfs: -30.0,
                good_dbfs: -18.0,
                hot_dbfs: -6.0,
            }),
        }
    }
}
impl Config {
    pub fn validate(&self) -> Result<(), String> {
        if self.version != 1 {
            return Err(format!("unsupported config version {}", self.version));
        }
        if self.sample_rate != SAMPLE_RATE {
            return Err("sample_rate must be exactly 48000".into());
        }
        if self.input_channels.contains(&0) || {
            let mut x = self.input_channels;
            x.sort();
            x.windows(2).any(|w| w[0] == w[1])
        } {
            return Err(
                "input_channels must select eight distinct 1-based physical channels".into(),
            );
        }
        if self.output_channels.contains(&0) || self.output_channels[0] == self.output_channels[1] {
            return Err("output_channels must select two distinct 1-based channels".into());
        }
        if self.role_trims.iter().any(|x| !x.is_finite() || *x < 0.0)
            || !self.master_trim.is_finite()
            || self.master_trim < 0.0
        {
            return Err("trims must be finite and non-negative".into());
        }
        if ![64, 128].contains(&self.buffer_frames) {
            return Err("buffer_frames must be 64 or 128".into());
        }
        if self.meter_targets.iter().any(|t| {
            ![t.low_dbfs, t.good_dbfs, t.hot_dbfs]
                .iter()
                .all(|x| x.is_finite())
        }) {
            return Err("meter target windows must be finite placeholder values".into());
        }
        for (target, role) in self.meter_targets.iter().zip(Role::ALL) {
            if target.role != role.name() {
                return Err(format!(
                    "meter target {} must be named {}",
                    target.role,
                    role.name()
                ));
            }
            if !(target.low_dbfs < target.good_dbfs && target.good_dbfs < target.hot_dbfs) {
                return Err(format!(
                    "meter target thresholds for {} must be strictly increasing",
                    role.name()
                ));
            }
        }
        Ok(())
    }
    pub fn load(path: impl AsRef<Path>) -> Result<Self, String> {
        let s = fs::read_to_string(path).map_err(|e| e.to_string())?;
        let c: Self = toml::from_str(&s).map_err(|e| e.to_string())?;
        c.validate()?;
        Ok(c)
    }
    pub fn channel_role_table() -> [(&'static str, &'static [usize]); ROLE_COUNT] {
        Role::ALL.map(|r| (r.name(), r.channels()))
    }
}
