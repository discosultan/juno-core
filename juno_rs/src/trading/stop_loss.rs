use crate::{genetics::Chromosome, Candle};
use juno_derive_rs::*;
use rand::prelude::*;
use serde::{de::DeserializeOwned, Deserialize, Serialize};

pub trait StopLoss: Send + Sync {
    type Params: Chromosome + DeserializeOwned + Serialize;

    fn new(params: &Self::Params) -> Self;

    fn upside_hit(&self) -> bool {
        false
    }

    fn downside_hit(&self) -> bool {
        false
    }

    fn clear(&mut self, _candle: &Candle) {}

    fn update(&mut self, _candle: &Candle) {}
}

#[derive(Chromosome, Clone, Debug, Deserialize, Serialize)]
pub struct NoopTakeProfitParams {}

pub struct NoopStopLoss {}

impl StopLoss for NoopStopLoss {
    type Params = NoopTakeProfitParams;

    fn new(params: &Self::Params) -> Self {
        Self {}
    }
}

#[derive(Chromosome, Clone, Debug, Deserialize, Serialize)]
pub struct BasicStopLossParams {
    pub threshold: f64,
}

fn threshold(rng: &mut StdRng) -> f64 {
    rng.gen_range(0.01, 1.0)
}

pub struct BasicStopLoss {
    pub threshold: f64,
    close_at_position: f64,
    close: f64,
}

impl StopLoss for BasicStopLoss {
    type Params = BasicStopLossParams;

    fn new(params: &BasicStopLossParams) -> Self {
        Self {
            threshold: params.threshold,
            close_at_position: 0.0,
            close: 0.0,
        }
    }

    fn upside_hit(&self) -> bool {
        self.close <= self.close_at_position * (1.0 - self.threshold)
    }

    fn downside_hit(&self) -> bool {
        self.close >= self.close_at_position * (1.0 + self.threshold)
    }

    fn clear(&mut self, candle: &Candle) {
        self.close_at_position = candle.close;
    }

    fn update(&mut self, candle: &Candle) {
        self.close = candle.close;
    }
}

#[derive(Chromosome, Clone, Debug, Deserialize, Serialize)]
pub struct TrailingStopLossParams {
    pub threshold: f64,
}

pub struct TrailingStopLoss {
    pub threshold: f64,
    highest_close_since_position: f64,
    lowest_close_since_position: f64,
    close: f64,
}

impl StopLoss for TrailingStopLoss {
    type Params = TrailingStopLossParams;

    fn new(params: &TrailingStopLossParams) -> Self {
        Self {
            threshold: params.threshold,
            highest_close_since_position: 0.0,
            lowest_close_since_position: f64::MAX,
            close: 0.0,
        }
    }

    fn upside_hit(&self) -> bool {
        self.close <= self.highest_close_since_position * (1.0 - self.threshold)
    }

    fn downside_hit(&self) -> bool {
        self.close >= self.lowest_close_since_position * (1.0 + self.threshold)
    }

    fn clear(&mut self, candle: &Candle) {
        self.highest_close_since_position = candle.close;
        self.lowest_close_since_position = candle.close;
    }

    fn update(&mut self, candle: &Candle) {
        self.close = candle.close;
        self.highest_close_since_position =
            f64::max(self.highest_close_since_position, candle.close);
        self.lowest_close_since_position = f64::min(self.lowest_close_since_position, candle.close);
    }
}