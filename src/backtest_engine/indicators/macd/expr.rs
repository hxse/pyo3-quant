use super::super::utils::null_to_nan_expr;
use super::config::MACDConfig;
use crate::backtest_engine::indicators::ema::{ema_expr, EMAConfig};
use crate::error::QuantError;
use polars::lazy::dsl::{col, lit, when, Expr};
use polars::prelude::*;

/// MACD 表达式层（复用 EMA 表达式）。
pub fn macd_expr(
    config: &MACDConfig,
) -> Result<(Expr, Expr, Expr, Expr, Expr, Expr, Expr, Expr), QuantError> {
    let column_name = &config.column_name;
    let mut fast_period = config.fast_period;
    let mut slow_period = config.slow_period;
    let signal_period = config.signal_period;
    let macd_alias = &config.macd_alias;
    let signal_alias = &config.signal_alias;
    let hist_alias = &config.hist_alias;
    let fast_ema_name = &config.fast_ema_name;
    let slow_ema_name = &config.slow_ema_name;

    if slow_period < fast_period {
        std::mem::swap(&mut fast_period, &mut slow_period);
    }

    let start_offset_fast = slow_period - fast_period;

    let mut fast_config = EMAConfig::new(fast_period);
    fast_config.column_name = column_name.clone();
    fast_config.alias_name = fast_ema_name.clone();
    fast_config.processed_column_alias = format!("{}_processed_temp", fast_config.alias_name);
    fast_config.initial_value_temp = format!("{}_initial_value_temp", fast_config.alias_name);
    fast_config.start_offset = start_offset_fast;
    fast_config.ignore_nulls = false;
    let (processed_close_fast, fast_ema) = ema_expr(&fast_config)?;

    let mut slow_config = EMAConfig::new(slow_period);
    slow_config.column_name = column_name.clone();
    slow_config.alias_name = slow_ema_name.clone();
    slow_config.processed_column_alias = format!("{}_processed_temp", slow_config.alias_name);
    slow_config.initial_value_temp = format!("{}_initial_value_temp", slow_config.alias_name);
    slow_config.start_offset = 0;
    slow_config.ignore_nulls = false;
    let (processed_close_slow, slow_ema) = ema_expr(&slow_config)?;

    let macd = (fast_ema.clone() - slow_ema.clone())
        .cast(DataType::Float64)
        .alias(macd_alias);

    let start_offset_signal = slow_period - 1;
    let mut signal_config = EMAConfig::new(signal_period);
    signal_config.column_name = macd_alias.clone();
    signal_config.alias_name = signal_alias.clone();
    signal_config.processed_column_alias = format!("{}_processed_temp", signal_config.alias_name);
    signal_config.initial_value_temp = format!("{}_initial_value_temp", signal_config.alias_name);
    signal_config.start_offset = start_offset_signal;
    signal_config.ignore_nulls = false;
    let (processed_macd, signal) = ema_expr(&signal_config)?;

    let hist = (col(macd_alias) - col(signal_alias))
        .cast(DataType::Float64)
        .alias(hist_alias);

    Ok((
        processed_close_fast,
        processed_close_slow,
        fast_ema,
        slow_ema,
        macd,
        processed_macd,
        signal,
        hist,
    ))
}

/// 统一 null->nan 输出表达式。
pub(crate) fn final_null_to_nan_exprs(config: &MACDConfig) -> (Expr, Expr, Expr) {
    (
        null_to_nan_expr(&config.macd_alias),
        null_to_nan_expr(&config.signal_alias),
        null_to_nan_expr(&config.hist_alias),
    )
}

/// 将 warmup 区间置空。
pub(crate) fn warmup_mask_exprs(config: &MACDConfig) -> (Expr, Expr, Expr, i64, i64) {
    let mut slow_period = config.slow_period;
    let mut fast_period = config.fast_period;
    if slow_period < fast_period {
        std::mem::swap(&mut slow_period, &mut fast_period);
    }

    let slow_ema_lookback = slow_period - 1;
    let signal_lookback = config.signal_period - 1;
    let total_lookback = slow_ema_lookback + signal_lookback;

    let mask_macd_before_slow = when(
        col("index")
            .cast(DataType::Int64)
            .lt(lit(slow_ema_lookback)),
    )
    .then(lit(NULL))
    .otherwise(col(&config.macd_alias))
    .cast(DataType::Float64)
    .alias(&config.macd_alias);

    let mask_macd = when(col("index").cast(DataType::Int64).lt(lit(total_lookback)))
        .then(lit(NULL))
        .otherwise(col(&config.macd_alias))
        .cast(DataType::Float64)
        .alias(&config.macd_alias);

    let mask_signal = when(col("index").cast(DataType::Int64).lt(lit(total_lookback)))
        .then(lit(NULL))
        .otherwise(col(&config.signal_alias))
        .cast(DataType::Float64)
        .alias(&config.signal_alias);

    (
        mask_macd_before_slow,
        mask_macd,
        mask_signal,
        total_lookback,
        slow_ema_lookback,
    )
}
