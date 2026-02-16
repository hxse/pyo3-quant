use super::config::ADXConfig;
use super::expr::{adx_expr, final_null_to_nan_exprs};
use crate::error::QuantError;
use polars::prelude::*;

/// 构建 ADX 的惰性计算流程。
pub fn adx_lazy(mut lazy_df: LazyFrame, config: &ADXConfig) -> Result<LazyFrame, QuantError> {
    let index_col_name = "index";
    lazy_df = lazy_df.with_row_index(index_col_name, None);

    let expr_groups = adx_expr(config)?;
    for group in expr_groups {
        lazy_df = lazy_df.with_columns(group);
    }

    Ok(lazy_df.select(final_null_to_nan_exprs(config)))
}

/// 急切执行 ADX 计算并返回四个结果列。
pub fn adx_eager(
    df: &DataFrame,
    config: &ADXConfig,
) -> Result<(Series, Series, Series, Series), QuantError> {
    let lazy_df = df.clone().lazy();
    let df_with_adx = adx_lazy(lazy_df, config)?.collect().map_err(QuantError::from)?;

    let adx_series = df_with_adx
        .column(&config.adx_alias)?
        .as_materialized_series()
        .clone();
    let adxr_series = df_with_adx
        .column(&config.adxr_alias)?
        .as_materialized_series()
        .clone();
    let plus_dm_series = df_with_adx
        .column(&config.plus_dm_alias)?
        .as_materialized_series()
        .clone();
    let minus_dm_series = df_with_adx
        .column(&config.minus_dm_alias)?
        .as_materialized_series()
        .clone();

    Ok((adx_series, adxr_series, plus_dm_series, minus_dm_series))
}
