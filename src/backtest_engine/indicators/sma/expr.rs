use super::config::SMAConfig;
use crate::error::{IndicatorError, QuantError};
use polars::lazy::dsl::col;
use polars::prelude::*;

/// 返回计算 SMA 的表达式。
pub fn sma_expr(config: &SMAConfig) -> Result<Expr, QuantError> {
    let column_name = config.column_name.as_str();
    let alias_name = config.alias_name.as_str();
    let period = config.period;

    if period <= 0 {
        return Err(IndicatorError::InvalidParameter(
            "sma".to_string(),
            "Period must be positive for SMA calculation".to_string(),
        )
        .into());
    }

    let sma_expr = col(column_name)
        .cast(DataType::Float64)
        .rolling_mean(RollingOptionsFixedWindow {
            window_size: period as usize,
            min_periods: period as usize,
            weights: None,
            center: false,
            fn_params: None,
        })
        .alias(alias_name);

    Ok(sma_expr)
}
