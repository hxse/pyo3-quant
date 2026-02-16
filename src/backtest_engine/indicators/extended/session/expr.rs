use super::config::OpeningBarConfig;
use crate::error::QuantError;
use polars::lazy::dsl::{col, lit};
use polars::prelude::*;
use polars::series::ops::NullBehavior;

/// 返回开盘 K 线检测表达式。
pub fn opening_bar_expr(config: &OpeningBarConfig) -> Result<Expr, QuantError> {
    let threshold_ms = config.threshold_ms();
    let alias = config.alias_name.as_str();

    let expr = (col("time").diff(lit(1), NullBehavior::Ignore))
        .gt(lit(threshold_ms))
        .fill_null(lit(false))
        .cast(DataType::Float64)
        .alias(alias);

    Ok(expr)
}
