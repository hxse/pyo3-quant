use super::config::ERConfig;
use super::expr::er_expr;
use super::super::utils::null_to_nan_expr;
use crate::error::{IndicatorError, QuantError};
use polars::lazy::dsl::col;
use polars::prelude::*;

/// ER 惰性蓝图。
pub fn er_lazy(lazy_df: LazyFrame, config: &ERConfig) -> Result<LazyFrame, QuantError> {
    let er_expr = er_expr(config)?;
    let result_lazy_df = lazy_df
        .with_column(er_expr)
        .with_column(null_to_nan_expr(&config.alias_name));
    Ok(result_lazy_df)
}

/// ER 急切计算。
pub fn er_eager(ohlcv_df: &DataFrame, config: &ERConfig) -> Result<Series, QuantError> {
    if config.length <= 0 {
        return Err(IndicatorError::InvalidParameter(
            "er".to_string(),
            "Length must be positive".to_string(),
        )
        .into());
    }

    if ohlcv_df.height() == 0 {
        return Ok(Series::new_empty(
            config.alias_name.as_str().into(),
            &DataType::Float64,
        ));
    }

    if ohlcv_df.height() < (config.length + 1) as usize {
        return Err(IndicatorError::DataTooShort(
            "er".to_string(),
            config.length + 1,
            ohlcv_df.height() as i64,
        )
        .into());
    }

    let lazy_df = ohlcv_df.clone().lazy();
    let lazy_plan = er_lazy(lazy_df, config)?;

    let df = lazy_plan
        .select([col(&config.alias_name)])
        .collect()
        .map_err(QuantError::from)?;

    Ok(df
        .column(&config.alias_name)?
        .as_materialized_series()
        .clone())
}
