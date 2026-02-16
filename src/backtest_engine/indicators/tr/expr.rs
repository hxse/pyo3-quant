use super::config::TRConfig;
use super::super::utils::null_when_expr;
use crate::error::QuantError;
use polars::lazy::dsl::{col, lit, max_horizontal};
use polars::prelude::*;

/// 返回计算 TR (True Range) 的表达式。
pub fn tr_expr(config: &TRConfig) -> Result<Expr, QuantError> {
    let high_col = config.high_col.as_str();
    let low_col = config.low_col.as_str();
    let close_col = config.close_col.as_str();
    let alias_name = config.alias_name.as_str();

    // 1. 前一根收盘价
    let prev_close = col(close_col).shift(lit(1i64));

    // 2. 三种候选波幅
    let hl_abs = (col(high_col) - col(low_col)).abs();
    let hpc_abs = (col(high_col) - prev_close.clone()).abs();
    let lpc_abs = (prev_close.clone() - col(low_col)).abs();

    // 3. 取最大值作为 TR
    let tr_expr = max_horizontal(vec![hl_abs, hpc_abs, lpc_abs])?;

    // 4. 第一行 prev_close 为空，按现有规则产出空值
    let final_tr = null_when_expr(prev_close.is_null(), tr_expr).alias(alias_name);
    Ok(final_tr)
}
