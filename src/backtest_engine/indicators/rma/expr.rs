use super::config::RMAConfig;
use crate::error::QuantError;
use polars::lazy::dsl::col;
use polars::prelude::*;

/// 表达式层：直接对全序列应用 ewm_mean，不引入前导 NaN。
pub fn rma_expr(config: &RMAConfig) -> Result<Expr, QuantError> {
    let col_name = config.column_name.as_str();
    let alias_name = config.alias_name.as_str();
    let period = config.period;

    let rma_expr = col(col_name)
        .cast(DataType::Float64)
        .ewm_mean(EWMOptions {
            alpha: 1.0 / period as f64,
            adjust: false,
            bias: false,
            min_periods: 1,
            ignore_nulls: true,
        })
        .alias(alias_name);

    Ok(rma_expr)
}
