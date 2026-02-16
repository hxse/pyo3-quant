use super::config::RSIConfig;
use super::expr::rsi_expr;
use super::super::utils::null_to_nan_expr;
use crate::error::{IndicatorError, QuantError};
use polars::lazy::dsl::col;
use polars::prelude::*;

/// RSI 惰性蓝图：拼装中间列并输出最终 RSI 列。
pub fn rsi_lazy(lazy_df: LazyFrame, config: &RSIConfig) -> Result<LazyFrame, QuantError> {
    let (
        change_expr,
        gain_expr,
        loss_expr,
        processed_gain_expr,
        processed_loss_expr,
        avg_gain_expr,
        avg_loss_expr,
        rsi_expr,
    ) = rsi_expr(config)?;

    let result_lazy_df = lazy_df
        .with_row_index("index", None)
        .with_column(change_expr)
        .with_column(gain_expr)
        .with_column(loss_expr)
        .with_column(processed_gain_expr)
        .with_column(processed_loss_expr)
        .with_column(avg_gain_expr)
        .with_column(avg_loss_expr)
        .with_column(rsi_expr)
        .with_column(null_to_nan_expr(&config.alias_name));

    Ok(result_lazy_df)
}

/// RSI 急切计算。
pub fn rsi_eager(ohlcv_df: &DataFrame, config: &RSIConfig) -> Result<Series, QuantError> {
    if config.period <= 0 {
        return Err(IndicatorError::InvalidParameter(
            "rsi".to_string(),
            "Period must be positive".to_string(),
        )
        .into());
    }

    let series_len = ohlcv_df.height();
    if series_len == 0 {
        return Ok(Series::new_empty(
            config.alias_name.clone().into(),
            &DataType::Float64,
        ));
    }

    let n_periods = config.period as usize;
    if series_len <= n_periods {
        return Err(IndicatorError::DataTooShort(
            "rsi".to_string(),
            config.period,
            series_len as i64,
        )
        .into());
    }

    let lazy_df = ohlcv_df.clone().lazy();
    let lazy_plan = rsi_lazy(lazy_df, config)?;
    let df = lazy_plan
        .select([col(&config.alias_name)])
        .collect()
        .map_err(QuantError::from)?;

    Ok(df
        .column(&config.alias_name)?
        .as_materialized_series()
        .clone())
}
