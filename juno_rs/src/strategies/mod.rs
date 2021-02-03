mod double_ma;
mod double_ma_2;
mod double_ma_stoch;
mod four_week_rule;
mod macd;
mod rsi;
mod sig;
mod sig_osc;
mod single_ma;
mod stoch;
mod triple_ma;

pub use double_ma::{DoubleMA, DoubleMAParams, DoubleMAParamsContext};
pub use double_ma_2::{DoubleMA2, DoubleMA2Params};
pub use double_ma_stoch::{DoubleMAStoch, DoubleMAStochParams};
pub use four_week_rule::{FourWeekRule, FourWeekRuleParams};
pub use macd::{Macd, MacdParams};
pub use rsi::{Rsi, RsiParams};
pub use sig::{Sig, SigParams};
pub use sig_osc::{SigOsc, SigOscParams};
pub use single_ma::{SingleMA, SingleMAParams};
pub use stoch::{Stoch, StochParams, StochParamsContext};
pub use triple_ma::{TripleMA, TripleMAParams};

use crate::{
    genetics::Chromosome,
    indicators::{adler32, MA_CHOICES},
    Advice, Candle,
};
use rand::prelude::*;
use serde::{de::DeserializeOwned, Deserialize, Deserializer, Serialize, Serializer};
use std::cmp::min;

pub trait Strategy: Send + Sync {
    type Params: Chromosome + DeserializeOwned + Serialize;

    fn new(params: &Self::Params) -> Self;
    fn maturity(&self) -> u32;
    fn mature(&self) -> bool;
    fn update(&mut self, candle: &Candle);
}

pub trait Oscillator: Strategy {
    fn overbought(&self) -> bool;
    fn oversold(&self) -> bool;
}

pub trait Signal: Strategy {
    fn advice(&self) -> Advice;
}

#[derive(Clone, Copy, Debug, Deserialize, PartialEq, Serialize)]
pub enum MidTrendPolicy {
    Current,
    Previous,
    Ignore,
}

const MID_TREND_POLICY_CHOICES: [MidTrendPolicy; 3] = [
    MidTrendPolicy::Current,
    MidTrendPolicy::Previous,
    MidTrendPolicy::Ignore,
];

pub struct MidTrend {
    policy: MidTrendPolicy,
    previous: Option<Advice>,
    enabled: bool,
}

impl MidTrend {
    pub fn new(policy: MidTrendPolicy) -> Self {
        Self {
            policy,
            previous: None,
            enabled: true,
        }
    }

    pub fn maturity(&self) -> u32 {
        if self.policy == MidTrendPolicy::Current {
            0
        } else {
            1
        }
    }

    pub fn update(&mut self, value: Advice) -> Advice {
        if !self.enabled || self.policy != MidTrendPolicy::Ignore {
            return value;
        }

        let mut result = Advice::None;
        if self.previous.is_none() {
            self.previous = Some(value)
        } else if Some(value) != self.previous {
            self.enabled = false;
            result = value;
        }
        result
    }
}

struct Persistence {
    age: u32,
    level: u32,
    return_previous: bool,
    potential: Advice,
    previous: Advice,
}

impl Persistence {
    pub fn new(level: u32, return_previous: bool) -> Self {
        Self {
            age: 0,
            level,
            return_previous,
            potential: Advice::None,
            previous: Advice::None,
        }
    }

    pub fn maturity(&self) -> u32 {
        self.level
    }

    pub fn update(&mut self, value: Advice) -> Advice {
        if self.level == 0 {
            return value;
        }

        if value != self.potential {
            self.age = 0;
            self.potential = value;
        }

        let result = if self.age >= self.level {
            self.previous = self.potential;
            self.potential
        } else if self.return_previous {
            self.previous
        } else {
            Advice::None
        };

        self.age = min(self.age + 1, self.level);
        result
    }
}

pub struct Changed {
    previous: Advice,
    enabled: bool,
}

impl Changed {
    pub fn new(enabled: bool) -> Self {
        Self {
            previous: Advice::None,
            enabled,
        }
    }

    pub fn maturity(&self) -> u32 {
        0
    }

    pub fn update(&mut self, value: Advice) -> Advice {
        if !self.enabled {
            return value;
        }

        let result = if value != self.previous {
            value
        } else {
            Advice::None
        };
        self.previous = value;
        result
    }
}

pub fn combine(advice1: Advice, advice2: Advice) -> Advice {
    if advice1 == Advice::None || advice2 == Advice::None {
        Advice::None
    } else if advice1 == advice2 {
        advice1
    } else {
        Advice::Liquidate
    }
}

pub trait StdRngExt {
    fn gen_mid_trend_policy(&mut self) -> MidTrendPolicy;
    fn gen_ma(&mut self) -> u32;
}

impl StdRngExt for StdRng {
    fn gen_mid_trend_policy(&mut self) -> MidTrendPolicy {
        *MID_TREND_POLICY_CHOICES.choose(self).unwrap()
    }

    fn gen_ma(&mut self) -> u32 {
        MA_CHOICES[self.gen_range(0..MA_CHOICES.len())]
    }
}

fn ma_to_str(value: u32) -> &'static str {
    match value {
        adler32::ALMA => "alma",
        adler32::DEMA => "dema",
        adler32::EMA => "ema",
        adler32::EMA2 => "ema2",
        adler32::KAMA => "kama",
        adler32::SMA => "sma",
        adler32::SMMA => "smma",
        _ => panic!("unknown ma value: {}", value),
    }
}

fn str_to_ma(representation: &str) -> u32 {
    match representation {
        "alma" => adler32::ALMA,
        "dema" => adler32::DEMA,
        "ema" => adler32::EMA,
        "ema2" => adler32::EMA2,
        "kama" => adler32::KAMA,
        "sma" => adler32::SMA,
        "smma" => adler32::SMMA,
        _ => panic!("unknown ma representation: {}", representation),
    }
}

pub fn serialize_ma<S>(value: &u32, serializer: S) -> Result<S::Ok, S::Error>
where
    S: Serializer,
{
    serializer.serialize_str(ma_to_str(*value))
}

pub fn deserialize_ma<'de, D>(deserializer: D) -> Result<u32, D::Error>
where
    D: Deserializer<'de>,
{
    let representation: String = Deserialize::deserialize(deserializer)?;
    Ok(str_to_ma(&representation))
}

pub fn serialize_ma_option<S>(value: &Option<u32>, serializer: S) -> Result<S::Ok, S::Error>
where
    S: Serializer,
{
    match value {
        Some(value) => serializer.serialize_str(ma_to_str(*value)),
        None => serializer.serialize_none(),
    }
}

pub fn deserialize_ma_option<'de, D>(deserializer: D) -> Result<Option<u32>, D::Error>
where
    D: Deserializer<'de>,
{
    let representation: Option<String> = Deserialize::deserialize(deserializer)?;
    Ok(representation.map(|repr| str_to_ma(&repr)))
}
