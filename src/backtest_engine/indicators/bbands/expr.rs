use polars::lazy::dsl::{col, lit};
use polars::prelude::*;

use super::super::{
    sma::{sma_expr, SMAConfig},
    utils::null_to_nan_expr,
};
use super::config::BBandsConfig;
use crate::error::QuantError;

/// 返回布林带计算所需的表达式。
pub fn bbands_expr(
    config: &BBandsConfig,
) -> Result<(Expr, Expr, Expr, Expr, Expr, Expr), QuantError> {
    let col_name = config.close_col.as_str();
    let period = config.period;
    let std_multiplier = config.std_multiplier;

    let middle_alias = config.middle_band_alias.as_str();
    let std_dev_alias = config.std_dev_alias.as_str();
    let upper_alias = config.upper_band_alias.as_str();
    let lower_alias = config.lower_band_alias.as_str();
    let bandwidth_alias = config.bandwidth_alias.as_str();
    let percent_alias = config.percent_alias.as_str();

    let rolling_options = RollingOptionsFixedWindow {
        window_size: period as usize,
        min_periods: period as usize,
        weights: None,
        center: false,
        fn_params: Some(RollingFnParams::Var(RollingVarParams { ddof: 0 })),
    };

    // 1. 中轨复用 SMA 实现。
    let sma_config = SMAConfig {
        column_name: col_name.to_string(),
        alias_name: middle_alias.to_string(),
        period,
    };
    let middle_band_expr = sma_expr(&sma_config)?;

    // 2. 标准差。
    let std_dev_expr = col(col_name)
        .cast(DataType::Float64)
        .rolling_std(rolling_options)
        .alias(std_dev_alias);

    // 3/4. 上下轨。
    let upper_band_expr =
        (col(middle_alias) + lit(std_multiplier) * col(std_dev_alias)).alias(upper_alias);
    let lower_band_expr =
        (col(middle_alias) - lit(std_multiplier) * col(std_dev_alias)).alias(lower_alias);

    // 5. 带宽。
    let bandwidth_expr = (lit(100.0) * (col(upper_alias) - col(lower_alias)) / col(middle_alias))
        .alias(bandwidth_alias);

    // 6. %B。
    let percent_b_expr = ((col(col_name).cast(DataType::Float64) - col(lower_alias))
        / (col(upper_alias) - col(lower_alias)))
    .alias(percent_alias);

    Ok((
        middle_band_expr,
        std_dev_expr,
        upper_band_expr,
        lower_band_expr,
        bandwidth_expr,
        percent_b_expr,
    ))
}

/// 布林带惰性蓝图。
pub fn bbands_lazy(lazy_df: LazyFrame, config: &BBandsConfig) -> Result<LazyFrame, QuantError> {
    let (
        middle_band_expr,
        std_dev_expr,
        upper_band_expr,
        lower_band_expr,
        bandwidth_expr,
        percent_b_expr,
    ) = bbands_expr(config)?;

    let result_lazy_df = lazy_df
        .with_columns([middle_band_expr, std_dev_expr])
        .with_columns([upper_band_expr, lower_band_expr])
        .with_columns([bandwidth_expr, percent_b_expr])
        .with_columns([
            null_to_nan_expr(&config.lower_band_alias),
            null_to_nan_expr(&config.middle_band_alias),
            null_to_nan_expr(&config.upper_band_alias),
            null_to_nan_expr(&config.bandwidth_alias),
            null_to_nan_expr(&config.percent_alias),
        ]);

    Ok(result_lazy_df)
}
