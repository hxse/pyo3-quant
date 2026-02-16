use super::config::CCIConfig;
use super::expr::cci_expr;
use crate::error::{IndicatorError, QuantError};
use polars::lazy::dsl::col;
use polars::prelude::*;

use super::super::utils::null_to_nan_expr;

pub fn cci_lazy(lazy_df: LazyFrame, config: &CCIConfig) -> Result<LazyFrame, QuantError> {
    let cci_expr = cci_expr(config)?;
    let result_lazy_df = lazy_df
        .with_column(cci_expr)
        .with_column(null_to_nan_expr(&config.alias_name));
    Ok(result_lazy_df)
}

pub fn cci_eager(ohlcv_df: &DataFrame, config: &CCIConfig) -> Result<Series, QuantError> {
    if config.period <= 0 {
        return Err(IndicatorError::InvalidParameter(
            "cci".to_string(),
            "Period must be positive".to_string(),
        )
        .into());
    }

    if ohlcv_df.height() == 0 {
        return Ok(Series::new_empty(
            config.alias_name.as_str().into(),
            &DataType::Float64,
        ));
    }

    if ohlcv_df.height() < config.period as usize {
        return Err(IndicatorError::DataTooShort(
            "cci".to_string(),
            config.period,
            ohlcv_df.height() as i64,
        )
        .into());
    }

    let lazy_df = ohlcv_df.clone().lazy();
    let lazy_plan = cci_lazy(lazy_df, config)?;

    let df = lazy_plan
        .select([col(&config.alias_name)])
        .collect()
        .map_err(QuantError::from)?;

    Ok(df.column(&config.alias_name)?.as_materialized_series().clone())
}
