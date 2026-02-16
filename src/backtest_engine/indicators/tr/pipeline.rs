use super::config::TRConfig;
use super::expr::tr_expr;
use super::super::utils::null_to_nan_expr;
use crate::error::QuantError;
use polars::lazy::dsl::col;
use polars::prelude::*;

/// TR 惰性蓝图。
pub fn tr_lazy(lazy_df: LazyFrame, config: &TRConfig) -> Result<LazyFrame, QuantError> {
    let tr_expr = tr_expr(config)?;
    let result_lazy_df = lazy_df
        .with_column(tr_expr)
        .with_column(null_to_nan_expr(config.alias_name.as_str()));
    Ok(result_lazy_df)
}

/// TR 急切计算。
pub fn tr_eager(ohlcv_df: &DataFrame, config: &TRConfig) -> Result<Series, QuantError> {
    if ohlcv_df.height() == 0 {
        return Ok(Series::new_empty(
            config.alias_name.as_str().into(),
            &DataType::Float64,
        ));
    }

    let lazy_df = ohlcv_df.clone().lazy();
    let lazy_plan = tr_lazy(lazy_df, config)?;
    let df = lazy_plan
        .select([col(config.alias_name.as_str())])
        .collect()
        .map_err(QuantError::from)?;

    Ok(df
        .column(config.alias_name.as_str())?
        .as_materialized_series()
        .clone())
}
