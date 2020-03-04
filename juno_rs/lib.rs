#![allow(dead_code)]

mod analyse;
mod trade;
mod common;
mod filters;
mod indicators;
mod math;
mod strategies;
mod trading;

use std::slice;
use crate::{
    analyse::analyse,
    indicators::{Dema, Ema, Ema2, MA, Sma, Smma},
    strategies::{Macd, MacdRsi, MAMACX, Strategy},
    trade::trade,
};
pub use crate::{
    common::{Advice, Candle, Fees},
    filters::Filters,
    trading::{Position, TradingSummary},
};

#[no_mangle]
pub unsafe extern "C" fn macd(
    trading_info: *const TradingInfo,
    macd_info: *const MacdInfo,
    analysis_info: *const AnalysisInfo,
) -> Result {
    let macd_info = &*macd_info;
    let strategy_factory = || {
        Macd::new(
            macd_info.short_period,
            macd_info.long_period,
            macd_info.signal_period,
            macd_info.persistence,
        )
    };
    run_test(trading_info, strategy_factory, analysis_info)
}

#[no_mangle]
pub unsafe extern "C" fn macdrsi(
    trading_info: *const TradingInfo,
    macdrsi_info: *const MacdRsiInfo,
    analysis_info: *const AnalysisInfo,
) -> Result {
    let macdrsi_info = &*macdrsi_info;
    let strategy_factory = || {
        MacdRsi::new(
            macdrsi_info.macd_short_period,
            macdrsi_info.macd_long_period,
            macdrsi_info.macd_signal_period,
            macdrsi_info.rsi_period,
            macdrsi_info.rsi_up_threshold,
            macdrsi_info.rsi_down_threshold,
            macdrsi_info.persistence,
        )
    };
    run_test(trading_info, strategy_factory, analysis_info)
}

// Adler32 of lowercased indicator name.
const EMA_: u32 = 40698164;
const EMA2: u32 = 64160102;
const SMA_: u32 = 43450690;
const SMMA: u32 = 72483247;
const DEMA: u32 = 66978200;

#[no_mangle]
pub unsafe extern "C" fn mamacx(
    trading_info: *const TradingInfo,
    mamacx_info: *const MAMACXInfo,
    analysis_info: *const AnalysisInfo,
) -> Result {
    let mamacx_info = &*mamacx_info;
    match (mamacx_info.short_ma, mamacx_info.long_ma) {
        (EMA_, EMA_) => run_mamacx_test::<Ema, Ema>  (trading_info, mamacx_info, analysis_info),
        (EMA_, EMA2) => run_mamacx_test::<Ema, Ema2> (trading_info, mamacx_info, analysis_info),
        (EMA_, SMA_) => run_mamacx_test::<Ema, Sma>  (trading_info, mamacx_info, analysis_info),
        (EMA_, SMMA) => run_mamacx_test::<Ema, Smma> (trading_info, mamacx_info, analysis_info),
        (EMA_, DEMA) => run_mamacx_test::<Ema, Dema> (trading_info, mamacx_info, analysis_info),
        (EMA2, EMA_) => run_mamacx_test::<Ema2, Ema> (trading_info, mamacx_info, analysis_info),
        (EMA2, EMA2) => run_mamacx_test::<Ema2, Ema2>(trading_info, mamacx_info, analysis_info),
        (EMA2, SMA_) => run_mamacx_test::<Ema2, Sma> (trading_info, mamacx_info, analysis_info),
        (EMA2, SMMA) => run_mamacx_test::<Ema2, Smma>(trading_info, mamacx_info, analysis_info),
        (EMA2, DEMA) => run_mamacx_test::<Ema2, Dema>(trading_info, mamacx_info, analysis_info),
        (SMA_, EMA_) => run_mamacx_test::<Sma, Ema>  (trading_info, mamacx_info, analysis_info),
        (SMA_, EMA2) => run_mamacx_test::<Sma, Ema2> (trading_info, mamacx_info, analysis_info),
        (SMA_, SMA_) => run_mamacx_test::<Sma, Sma>  (trading_info, mamacx_info, analysis_info),
        (SMA_, SMMA) => run_mamacx_test::<Sma, Smma> (trading_info, mamacx_info, analysis_info),
        (SMA_, DEMA) => run_mamacx_test::<Sma, Dema> (trading_info, mamacx_info, analysis_info),
        (SMMA, EMA_) => run_mamacx_test::<Smma, Ema> (trading_info, mamacx_info, analysis_info),
        (SMMA, EMA2) => run_mamacx_test::<Smma, Ema2>(trading_info, mamacx_info, analysis_info),
        (SMMA, SMA_) => run_mamacx_test::<Smma, Sma> (trading_info, mamacx_info, analysis_info),
        (SMMA, SMMA) => run_mamacx_test::<Smma, Smma>(trading_info, mamacx_info, analysis_info),
        (SMMA, DEMA) => run_mamacx_test::<Smma, Dema>(trading_info, mamacx_info, analysis_info),
        (DEMA, EMA_) => run_mamacx_test::<Dema, Ema> (trading_info, mamacx_info, analysis_info),
        (DEMA, EMA2) => run_mamacx_test::<Dema, Ema2>(trading_info, mamacx_info, analysis_info),
        (DEMA, SMA_) => run_mamacx_test::<Dema, Sma> (trading_info, mamacx_info, analysis_info),
        (DEMA, SMMA) => run_mamacx_test::<Dema, Smma>(trading_info, mamacx_info, analysis_info),
        (DEMA, DEMA) => run_mamacx_test::<Dema, Dema>(trading_info, mamacx_info, analysis_info),
        _ => panic!(
            "Moving average ({}, {}) not implemented!",
            mamacx_info.short_ma,
            mamacx_info.long_ma
        ),
    }
}

unsafe fn run_mamacx_test<TShort: MA, TLong: MA>(
    trading_info: *const TradingInfo,
    mamacx_info: &MAMACXInfo,
    analysis_info: *const AnalysisInfo,
) -> Result {
    let strategy_factory = || {
        MAMACX::new(
            TShort::new(mamacx_info.short_period),
            TLong::new(mamacx_info.long_period),
            mamacx_info.neg_threshold,
            mamacx_info.pos_threshold,
            mamacx_info.persistence,
        )
    };
    run_test(trading_info, strategy_factory, analysis_info)
}

unsafe fn run_test<TF: Fn() -> TS, TS: Strategy>(
    trading_info: *const TradingInfo,
    strategy_factory: TF,
    analysis_info: *const AnalysisInfo,
) -> Result {
    // Trading.
    // Turn unsafe ptrs to safe references.
    let trading_info = &*trading_info;
    let candles = slice::from_raw_parts(trading_info.candles, trading_info.candles_length as usize);
    let fees = &*trading_info.fees;
    let filters = &*trading_info.filters;

    let trading_result = trade(
        strategy_factory,
        candles,
        fees,
        filters,
        trading_info.interval,
        trading_info.quote,
        trading_info.missed_candle_policy,
        trading_info.trailing_stop,
    );

    // Analysis.
    let analysis_info = &*analysis_info;
    let quote_fiat_daily = slice::from_raw_parts(
        analysis_info.quote_fiat_daily, 
        analysis_info.quote_fiat_daily_length as usize
    );
    let base_fiat_daily = slice::from_raw_parts(
        analysis_info.base_fiat_daily, 
        analysis_info.base_fiat_daily_length as usize
    );
    let benchmark_g_returns = slice::from_raw_parts(
        analysis_info.benchmark_g_returns,
        analysis_info.benchmark_g_returns_length as usize
    );

    let analysis_result = analyse(
        quote_fiat_daily,
        base_fiat_daily,
        benchmark_g_returns,
        &trading_result
    );

    // Combine.
    Result(
        analysis_result.0,
        // trading_result.profit,
        // trading_result.mean_drawdown,
        // trading_result.max_drawdown,
        // trading_result.mean_position_profit,
        // trading_result.mean_position_duration,
        // trading_result.num_positions_in_profit,
        // trading_result.num_positions_in_loss,
    )
}

#[repr(C)]
pub struct Result(f64, ); // (f64, f64, f64, f64, f64, u64, u32, u32);

#[repr(C)]
pub struct AnalysisInfo {
    quote_fiat_daily: *const f64,
    quote_fiat_daily_length: u32,
    base_fiat_daily: *const f64,
    base_fiat_daily_length: u32,
    benchmark_g_returns: *const f64,
    benchmark_g_returns_length: u32,
}

#[repr(C)]
pub struct TradingInfo {
    candles: *const Candle,
    candles_length: u32,
    fees: *const Fees,
    filters: *const Filters,
    interval: u64,
    quote: f64,
    missed_candle_policy: u32,
    trailing_stop: f64,
}

#[repr(C)]
pub struct MacdInfo {
    short_period: u32,
    long_period: u32,
    signal_period: u32,
    persistence: u32,
}

#[repr(C)]
pub struct MacdRsiInfo {
    macd_short_period: u32,
    macd_long_period: u32,
    macd_signal_period: u32,
    rsi_period: u32,
    rsi_up_threshold: f64,
    rsi_down_threshold: f64,
    persistence: u32,
}

#[repr(C)]
pub struct MAMACXInfo {
    short_period: u32,
    long_period: u32,
    neg_threshold: f64,
    pos_threshold: f64,
    persistence: u32,
    short_ma: u32,
    long_ma: u32,
}
