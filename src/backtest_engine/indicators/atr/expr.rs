use super::config::ATRConfig;
use crate::backtest_engine::indicators::tr::{tr_expr, TRConfig};
use crate::error::QuantError;
use polars::lazy::dsl::{col, lit};
use polars::prelude::*;

use super::super::utils::null_when_expr;

/// 返回计算 ATR 所需的核心表达式。
pub fn atr_expr(config: &ATRConfig) -> Result<(Expr, Expr), QuantError> {
    let alias_name = config.alias_name.as_str();
    let period = config.period;

    let tr_temp_name = "tr_temp";
    let initial_value_temp_name = "atr_initial_value_temp";
    let processed_tr_temp_name = "processed_tr_temp";
    let index_col_name = "index";

    let sma_initial_value_expr = col(tr_temp_name)
        .slice(1, period as u32)
        .mean()
        .alias(initial_value_temp_name);

    let processed_tr_expr = null_when_expr(
        col(index_col_name).cast(DataType::Int64).lt(lit(period)),
        when(col(index_col_name).cast(DataType::Int64).eq(lit(period)))
            .then(sma_initial_value_expr)
            .otherwise(col(tr_temp_name)),
    )
    .alias(processed_tr_temp_name);

    let atr_expr = col(processed_tr_temp_name)
        .ewm_mean(EWMOptions {
            alpha: 1.0 / (period as f64),
            adjust: false,
            bias: false,
            min_periods: 1,
            ignore_nulls: true,
        })
        .alias(alias_name);

    Ok((processed_tr_expr, atr_expr))
}

/// 构建 ATR 的 TR 临时表达式。
pub(crate) fn tr_temp_expr(config: &ATRConfig) -> Result<Expr, QuantError> {
    tr_expr(&TRConfig {
        high_col: config.high_col.clone(),
        low_col: config.low_col.clone(),
        close_col: config.close_col.clone(),
        alias_name: "tr_temp".to_string(),
    })
}
