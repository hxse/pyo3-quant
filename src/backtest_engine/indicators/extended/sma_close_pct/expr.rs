use crate::error::QuantError;
use polars::lazy::dsl::{col, lit};
use polars::prelude::*;

/// 返回收盘价相对 SMA 百分比表达式。
pub fn sma_close_pct_expr(sma_col_name: &str, alias_name: &str) -> Result<Expr, QuantError> {
    let pct_expr = ((col("close") - col(sma_col_name)) / col(sma_col_name)) * lit(100.0);
    Ok(pct_expr.alias(alias_name))
}
