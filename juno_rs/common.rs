use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use crate::filters::Filters;

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Advice {
    None,
    Long,
    Short,
    Liquidate,
}

#[derive(Debug, Deserialize, Serialize)]
#[repr(C)]
pub struct BorrowInfo {
    pub daily_interest_rate: f64,
    pub limit: f64,
}

#[derive(Debug, Clone, Copy)]
#[repr(C)]
pub struct Candle {
    pub time: u64,
    pub open: f64,
    pub high: f64,
    pub low: f64,
    pub close: f64,
    pub volume: f64,
}

#[derive(Debug, Deserialize, Serialize)]
#[repr(C)]
pub struct Fees {
    pub maker: f64,
    pub taker: f64,
}

#[derive(Deserialize, Serialize)]
pub struct ExchangeInfo {
    pub fees: HashMap<String, Fees>,
    pub filters: HashMap<String, Filters>,
    pub borrow_info: HashMap<String, HashMap<String, BorrowInfo>>,
}
