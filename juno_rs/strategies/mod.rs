mod macd;
mod macdrsi;
mod mamacx;
mod rsi;

pub use macd::Macd;
pub use macdrsi::MacdRsi;
pub use mamacx::MAMACX;
pub use rsi::Rsi;
use std::cmp::min;

use crate::{Advice, Candle};

pub trait Strategy {
    fn update(&mut self, candle: &Candle) -> Advice;
}

struct MidTrend {
    ignore: bool,
    previous: Option<Advice>,
    maturity: u32,
}

impl MidTrend {
    pub fn new(ignore: bool) -> Self {
        Self {
            ignore,
            previous: None,
            maturity: if ignore { 1 } else { 0 },
        }
    }

    pub fn maturity(&self) -> u32 {
        self.maturity
    }

    pub fn update(&mut self, value: Advice) -> Advice {
        if !self.ignore {
            return value;
        }

        let mut result = Advice::None;
        if self.previous.is_none() {
            self.previous = Some(value)
        } else if Some(value) != self.previous {
            self.ignore = false;
            result = value;
        }
        return result
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
