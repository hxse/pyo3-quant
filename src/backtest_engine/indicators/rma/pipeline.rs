use super::config::RMAConfig;
use super::expr::rma_expr;
use super::super::utils::null_to_nan_expr;
use crate::error::{IndicatorError, QuantError};
use polars::lazy::dsl::col;
use polars::prelude::*;

/// 蓝图层：注入 RMA 列并统一将 NULL 转为 NaN。
pub fn rma_lazy(lazy_df: LazyFrame, config: &RMAConfig) -> Result<LazyFrame, QuantError> {
    let rma_expr = rma_expr(config)?;
    let result_lazy_df = lazy_df
        .with_column(rma_expr)
        .with_column(null_to_nan_expr(&config.alias_name));
    Ok(result_lazy_df)
}

/// 计算层：参数校验后执行惰性计划并提取目标列。
pub fn rma_eager(ohlcv_df: &DataFrame, config: &RMAConfig) -> Result<Series, QuantError> {
    let period = config.period;
    if period <= 0 {
        return Err(IndicatorError::InvalidParameter(
            "rma".to_string(),
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

    let n_periods = period as usize;
    if series_len < n_periods {
        return Err(
            IndicatorError::DataTooShort("rma".to_string(), period, series_len as i64).into(),
        );
    }

    let lazy_df = ohlcv_df.clone().lazy();
    let lazy_plan = rma_lazy(lazy_df, config)?;
    let result_df = lazy_plan.select([col(&config.alias_name)]).collect()?;

    Ok(result_df
        .column(&config.alias_name)?
        .as_materialized_series()
        .clone())
}
