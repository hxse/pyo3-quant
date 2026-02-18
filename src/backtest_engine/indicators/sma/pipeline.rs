use super::super::utils::null_to_nan_expr;
use super::config::SMAConfig;
use super::expr::sma_expr;
use crate::error::{IndicatorError, QuantError};
use polars::lazy::dsl::col;
use polars::prelude::*;

/// SMA 惰性蓝图。
pub fn sma_lazy(lazy_df: LazyFrame, config: &SMAConfig) -> Result<LazyFrame, QuantError> {
    let sma_expr = sma_expr(config)?;
    let result_lazy_df = lazy_df
        .with_column(sma_expr)
        .with_column(null_to_nan_expr(&config.alias_name));
    Ok(result_lazy_df)
}

/// SMA 急切计算。
pub fn sma_eager(ohlcv_df: &DataFrame, config: &SMAConfig) -> Result<Series, QuantError> {
    if config.period <= 0 {
        return Err(IndicatorError::InvalidParameter(
            "sma".to_string(),
            "Period must be positive for SMA calculation".to_string(),
        )
        .into());
    }

    if ohlcv_df.height() == 0 {
        return Ok(Series::new_empty(
            config.alias_name.as_str().into(),
            &DataType::Float64,
        ));
    }

    let lazy_df = ohlcv_df.clone().lazy();
    let lazy_plan = sma_lazy(lazy_df, config)?;
    let df = lazy_plan
        .select([col(config.alias_name.as_str())])
        .collect()
        .map_err(QuantError::from)?;

    Ok(df
        .column(config.alias_name.as_str())?
        .as_materialized_series()
        .clone())
}
