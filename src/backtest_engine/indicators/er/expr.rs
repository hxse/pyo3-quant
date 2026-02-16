use super::config::ERConfig;
use crate::error::QuantError;
use polars::lazy::dsl::col;
use polars::prelude::*;

/// 返回 ER 计算表达式。
pub fn er_expr(config: &ERConfig) -> Result<Expr, QuantError> {
    let close = col(&config.close_col);
    let length = config.length;
    let drift = config.drift;

    // 1. abs_diff = |close[i] - close[i-length]|
    let abs_diff = close.clone().diff(lit(length), Default::default()).abs();

    // 2. abs_volatility = |close[i] - close[i-drift]|
    let abs_volatility = close.diff(lit(drift), Default::default()).abs();

    // 3. abs_volatility_rsum = rolling_sum(abs_volatility, length)
    let abs_volatility_rsum = abs_volatility.rolling_sum(RollingOptionsFixedWindow {
        window_size: length as usize,
        min_periods: length as usize,
        weights: None,
        center: false,
        fn_params: None,
    });

    // 4. ER = abs_diff / abs_volatility_rsum
    let er_expr = abs_diff / abs_volatility_rsum;
    Ok(er_expr.alias(&config.alias_name))
}
