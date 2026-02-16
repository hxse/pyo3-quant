use super::config::SmaClosePctConfig;
use super::expr::sma_close_pct_expr;
use crate::backtest_engine::indicators::{
    sma::{sma_eager, SMAConfig},
    utils::null_to_nan_expr,
};
use crate::error::QuantError;
use polars::lazy::dsl::lit;
use polars::prelude::*;

/// 计算收盘价相对 SMA 的百分比序列。
pub fn sma_close_pct_eager(
    ohlcv_df: &DataFrame,
    config: &SmaClosePctConfig,
) -> Result<Series, QuantError> {
    // 先复用已有 SMA 计算，保持与主 SMA 指标同一语义。
    let sma_config = SMAConfig::new(config.period);
    let sma_series = sma_eager(ohlcv_df, &sma_config)?;
    let sma_col_name = sma_series.name().to_string();

    let lazy_df = ohlcv_df
        .clone()
        .lazy()
        .with_column(lit(sma_series).alias(&sma_col_name));

    let result_df = lazy_df
        .select(&[sma_close_pct_expr(&sma_col_name, &config.alias_name)?])
        .with_columns(&[null_to_nan_expr(&config.alias_name)])
        .collect()
        .map_err(QuantError::from)?;

    Ok(result_df
        .column(&config.alias_name)?
        .as_materialized_series()
        .clone())
}
