use super::{
    AdviceFilters,
    deserialize_mid_trend_policy, serialize_mid_trend_policy, Oscillator, Signal, StdRngExt,
    Strategy,
};
use crate::{
    genetics::Chromosome,
    strategies::{combine, MidTrend, Persistence},
    Advice, Candle,
};
use juno_derive_rs::*;
use rand::prelude::*;
use serde::{Deserialize, Deserializer, Serialize, Serializer};
use std::cmp::{max, min};

const OSC_FILTER_ENFORCE: u32 = 0;
const OSC_FILTER_PREVENT: u32 = 1;

fn serialize_osc_filter<S>(value: &u32, serializer: S) -> Result<S::Ok, S::Error>
where
    S: Serializer,
{
    let representation = match *value {
        OSC_FILTER_ENFORCE => "enforce",
        OSC_FILTER_PREVENT => "prevent",
        _ => panic!("unknown oscillator filter value: {}", value),
    };
    serializer.serialize_str(representation)
}

fn deserialize_osc_filter<'de, D>(deserializer: D) -> Result<u32, D::Error>
where
    D: Deserializer<'de>,
{
    let representation: String = Deserialize::deserialize(deserializer)?;
    Ok(match representation.as_ref() {
        "enforce" => OSC_FILTER_ENFORCE,
        "prevent" => OSC_FILTER_PREVENT,
        _ => panic!(
            "unknown oscillator filter representation: {}",
            representation
        ),
    })
}

#[derive(Clone, Debug, Deserialize, Serialize)]
pub struct SigOscParams<S: Chromosome, O: Chromosome> {
    pub sig: S,
    pub osc: O,
    #[serde(serialize_with = "serialize_osc_filter")]
    #[serde(deserialize_with = "deserialize_osc_filter")]
    pub osc_filter: u32,
    pub persistence: u32,
    #[serde(serialize_with = "serialize_mid_trend_policy")]
    #[serde(deserialize_with = "deserialize_mid_trend_policy")]
    pub mid_trend_policy: u32,
}

impl<S: Chromosome, O: Chromosome> Chromosome for SigOscParams<S, O> {
    fn len() -> usize {
        S::len() + O::len() + 3
    }

    fn generate(rng: &mut StdRng) -> Self {
        Self {
            sig: S::generate(rng),
            osc: O::generate(rng),
            osc_filter: gen_osc_filter(rng),
            persistence: gen_persistence(rng),
            mid_trend_policy: rng.gen_mid_trend_policy(),
        }
    }

    fn cross(&mut self, other: &mut Self, mut i: usize) {
        if i < S::len() {
            self.sig.cross(&mut other.sig, i);
            return;
        }
        i -= S::len();
        if i < O::len() {
            self.osc.cross(&mut other.osc, i);
            return;
        }
        i -= O::len();
        match i {
            0 => std::mem::swap(&mut self.osc_filter, &mut other.osc_filter),
            1 => std::mem::swap(&mut self.persistence, &mut other.persistence),
            2 => std::mem::swap(&mut self.mid_trend_policy, &mut other.mid_trend_policy),
            _ => panic!("index out of bounds"),
        }
    }

    fn mutate(&mut self, rng: &mut StdRng, mut i: usize) {
        if i < S::len() {
            self.sig.mutate(rng, i);
            return;
        }
        i -= S::len();
        if i < O::len() {
            self.osc.mutate(rng, i);
            return;
        }
        i -= O::len();
        match i {
            0 => self.osc_filter = gen_osc_filter(rng),
            1 => self.persistence = gen_persistence(rng),
            2 => self.mid_trend_policy = rng.gen_mid_trend_policy(),
            _ => panic!("index out of bounds"),
        }
    }
}

fn gen_osc_filter(rng: &mut StdRng) -> u32 {
    if rng.gen_bool(0.5) {
        OSC_FILTER_ENFORCE
    } else {
        OSC_FILTER_PREVENT
    }
}
fn gen_persistence(rng: &mut StdRng) -> u32 {
    rng.gen_range(0..10)
}

#[derive(Signal)]
pub struct SigOsc<S: Signal, O: Oscillator> {
    sig: S,
    osc: O,
    osc_filter: u32,
    advice: Advice,
    mid_trend: MidTrend,
    persistence: Persistence,
    t: u32,
    t1: u32,
}

impl<S: Signal, O: Oscillator> SigOsc<S, O> {
    fn filter(&self, advice: Advice) -> Advice {
        match self.osc_filter {
            OSC_FILTER_ENFORCE => self.filter_enforce(advice),
            OSC_FILTER_PREVENT => self.filter_prevent(advice),
            _ => panic!("Invalid osc_filter: {}", self.osc_filter),
        }
    }

    fn filter_enforce(&self, advice: Advice) -> Advice {
        match advice {
            Advice::None => Advice::None,
            Advice::Liquidate => Advice::Liquidate,
            Advice::Long => {
                if self.osc.oversold() {
                    Advice::Long
                } else {
                    Advice::Liquidate
                }
            }
            Advice::Short => {
                if self.osc.overbought() {
                    Advice::Short
                } else {
                    Advice::Liquidate
                }
            }
        }
    }

    fn filter_prevent(&self, advice: Advice) -> Advice {
        match advice {
            Advice::None => Advice::None,
            Advice::Liquidate => Advice::Liquidate,
            Advice::Long => {
                if self.osc.overbought() {
                    Advice::Liquidate
                } else {
                    Advice::Long
                }
            }
            Advice::Short => {
                if self.osc.oversold() {
                    Advice::Liquidate
                } else {
                    Advice::Short
                }
            }
        }
    }
}

impl<S: Signal, O: Oscillator> Strategy for SigOsc<S, O> {
    type Params = SigOscParams<S::Params, O::Params>;

    fn new(params: &Self::Params) -> Self {
        let sig = S::new(&params.sig);
        let osc = O::new(&params.osc);
        let mid_trend = MidTrend::new(params.mid_trend_policy);
        let persistence = Persistence::new(params.persistence, false);
        Self {
            advice: Advice::None,
            t: 0,
            t1: max(sig.maturity(), osc.maturity())
                + max(mid_trend.maturity(), persistence.maturity())
                - 1,
            sig,
            osc,
            osc_filter: params.osc_filter,
            mid_trend,
            persistence,
        }
    }

    fn maturity(&self) -> u32 {
        self.t1
    }

    fn mature(&self) -> bool {
        self.t >= self.t1
    }

    fn update(&mut self, candle: &Candle) {
        self.t = min(self.t + 1, self.t1);

        self.sig.update(candle);
        self.osc.update(candle);

        if self.sig.mature() && self.osc.mature() {
            let advice = self.filter(self.sig.advice());
            self.advice = combine(
                self.mid_trend.update(advice),
                self.persistence.update(advice),
            );
        }
    }
}
