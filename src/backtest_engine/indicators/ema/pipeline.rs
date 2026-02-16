use super::config::EMAConfig;
use super::expr::ema_expr;
use crate::error::{IndicatorError, QuantError};
use polars::lazy::dsl::col;
use polars::prelude::*;

use super::super::utils::null_to_nan_expr;

pub fn ema_lazy(lazy_df: LazyFrame, config: &EMAConfig) -> Result<LazyFrame, QuantError> {
    let (processed_close_expr, ema_expr) = ema_expr(config)?;
    let result_lazy_df = lazy_df
        .with_row_index("index", None)
        .with_column(processed_close_expr)
        .with_column(ema_expr)
        .with_column(null_to_nan_expr(&config.alias_name));
    Ok(result_lazy_df)
}

pub fn ema_eager(ohlcv_df: &DataFrame, config: &EMAConfig) -> Result<Series, QuantError> {
    let alias_name = &config.alias_name;
    if config.period <= 0 {
        return Err(IndicatorError::InvalidParameter(
            alias_name.to_string(),
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
    if series_len < n_periods {
        return Err(IndicatorError::DataTooShort(
            alias_name.to_string(),
            config.period,
            series_len as i64,
        )
        .into());
    }

    let lazy_df = ohlcv_df.clone().lazy();
    let lazy_plan = ema_lazy(lazy_df, config)?;
    let result_df = lazy_plan
        .select([col(alias_name)])
        .collect()
        .map_err(QuantError::from)?;

    Ok(result_df
        .column(alias_name)
        .map_err(QuantError::from)?
        .as_materialized_series()
        .clone())
}
