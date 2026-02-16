use super::config::ATRConfig;
use super::expr::{atr_expr, tr_temp_expr};
use crate::error::{IndicatorError, QuantError};
use polars::lazy::dsl::col;
use polars::prelude::*;

use super::super::utils::null_to_nan_expr;

/// ATR 惰性蓝图。
pub fn atr_lazy(lazy_df: LazyFrame, config: &ATRConfig) -> Result<LazyFrame, QuantError> {
    let (processed_tr_expr, atr_expr) = atr_expr(config)?;

    let result_lazy_df = lazy_df
        .with_row_index("index", None)
        .with_column(tr_temp_expr(config)?)
        .with_column(processed_tr_expr)
        .with_column(atr_expr)
        .select(&[
            col(&config.high_col),
            col(&config.low_col),
            col(&config.close_col),
            null_to_nan_expr(&config.alias_name),
        ]);

    Ok(result_lazy_df)
}

/// ATR 急切计算。
pub fn atr_eager(ohlcv_df: &DataFrame, config: &ATRConfig) -> Result<Series, QuantError> {
    let period = config.period;
    let alias_name = &config.alias_name;

    if period <= 0 {
        return Err(IndicatorError::InvalidParameter(
            alias_name.to_string(),
            "Period must be positive".to_string(),
        )
        .into());
    }

    let series_len = ohlcv_df.height();
    if series_len == 0 {
        return Err(
            IndicatorError::DataTooShort(alias_name.to_string(), 0, series_len as i64).into(),
        );
    }

    let n_periods = period as usize;
    if series_len < n_periods {
        return Err(IndicatorError::DataTooShort(
            alias_name.to_string(),
            period,
            series_len as i64,
        )
        .into());
    }

    let lazy_df = ohlcv_df.clone().lazy();
    let lazy_plan = atr_lazy(lazy_df, config)?;
    let df = lazy_plan
        .select([col(alias_name)])
        .collect()
        .map_err(QuantError::from)?;

    Ok(df.column(alias_name)?.as_materialized_series().clone())
}
