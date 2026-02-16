use super::config::OpeningBarConfig;
use super::expr::opening_bar_expr;
use crate::error::QuantError;
use polars::lazy::dsl::col;
use polars::prelude::*;

/// 开盘 K 线检测惰性蓝图。
pub fn opening_bar_lazy(
    lazy_df: LazyFrame,
    config: &OpeningBarConfig,
) -> Result<LazyFrame, QuantError> {
    let expr = opening_bar_expr(config)?;
    let result_lazy_df = lazy_df.with_column(expr);
    Ok(result_lazy_df)
}

/// 开盘 K 线检测急切计算。
pub fn opening_bar_eager(
    ohlcv_df: &DataFrame,
    config: &OpeningBarConfig,
) -> Result<Series, QuantError> {
    let lazy_df = ohlcv_df.clone().lazy();
    let result_df = opening_bar_lazy(lazy_df, config)?
        .select([col(&config.alias_name)])
        .collect()?;

    Ok(result_df
        .column(&config.alias_name)?
        .as_materialized_series()
        .clone())
}
