use super::config::EMAConfig;
use crate::error::QuantError;
use polars::lazy::dsl::{col, lit, when, Expr};
use polars::prelude::*;

/// 返回计算 EMA 所需的表达式。
pub fn ema_expr(config: &EMAConfig) -> Result<(Expr, Expr), QuantError> {
    let col_name = config.column_name.as_str();
    let alias_name = config.alias_name.as_str();
    let period = config.period;
    let processed_column_alias = config.processed_column_alias.as_str();
    let initial_value_temp_name = config.initial_value_temp.as_str();
    let index_col_name = "index";
    let start_offset = config.start_offset;
    let alpha = 2.0 / (period as f64 + 1.0);

    let sma_initial_value_expr = col(col_name)
        .slice(lit(start_offset), lit(period as u32))
        .mean()
        .cast(DataType::Float64)
        .alias(initial_value_temp_name);

    let initial_idx = start_offset + period - 1;

    let processed_expr = when(
        col(index_col_name)
            .cast(DataType::Int64)
            .lt(lit(initial_idx)),
    )
    .then(lit(NULL))
    .when(
        col(index_col_name)
            .cast(DataType::Int64)
            .eq(lit(initial_idx)),
    )
    .then(sma_initial_value_expr)
    .otherwise(col(col_name).cast(DataType::Float64))
    .alias(processed_column_alias);

    let ema_expr = col(processed_column_alias)
        .ewm_mean(EWMOptions {
            alpha,
            adjust: false,
            bias: false,
            min_periods: 1,
            ignore_nulls: config.ignore_nulls,
        })
        .cast(DataType::Float64)
        .alias(alias_name);

    Ok((processed_expr, ema_expr))
}
