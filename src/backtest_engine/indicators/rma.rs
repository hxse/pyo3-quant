// src/backtest_engine/indicators/rma.rs
use super::registry::Indicator;
use super::utils::null_to_nan_expr;
use crate::error::{IndicatorError, QuantError};
use crate::types::Param;
use polars::lazy::dsl::col;
use polars::prelude::*;
use std::collections::HashMap;

pub struct RMAConfig {
    pub period: i64,
    pub column_name: String,
    pub alias_name: String,
}

impl RMAConfig {
    pub fn new(period: i64) -> Self {
        Self {
            period,
            column_name: "close".to_string(),
            alias_name: "rma".to_string(),
        }
    }
}

// 表达式层: 直接使用ewm,无前导NaN
pub fn rma_expr(config: &RMAConfig) -> Result<Expr, QuantError> {
    let col_name = config.column_name.as_str();
    let alias_name = config.alias_name.as_str();
    let period = config.period;

    // 直接对整个序列使用ewm_mean,无需任何预处理
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

// 蓝图层: 简化,不需要row_index
pub fn rma_lazy(lazy_df: LazyFrame, config: &RMAConfig) -> Result<LazyFrame, QuantError> {
    let rma_expr = rma_expr(config)?;
    let result_lazy_df = lazy_df
        .with_column(rma_expr)
        // 在蓝图层将 RMA 结果的 NULL 转换为 NaN
        .with_column(null_to_nan_expr(&config.alias_name));

    Ok(result_lazy_df)
}

// 计算层: 保持不变
pub fn rma_eager(ohlcv_df: &DataFrame, config: &RMAConfig) -> Result<Series, QuantError> {
    let period = config.period;
    if period <= 0 {
        return Err(IndicatorError::InvalidParameter(
            "rma".to_string(),
            "Period must be positive".to_string(),
        )
        .into());
    }
    let series_len = ohlcv_df.height();
    if series_len == 0 {
        return Ok(Series::new_empty(
            config.alias_name.clone().into(),
            &DataType::Float64,
        ));
    }
    let n_periods = period as usize;
    if series_len < n_periods {
        return Err(
            IndicatorError::DataTooShort("rma".to_string(), period, series_len as i64).into(),
        );
    }

    let lazy_df = ohlcv_df.clone().lazy();
    let lazy_plan = rma_lazy(lazy_df, config)?;
    let result_df = lazy_plan.select([col(&config.alias_name)]).collect()?;

    Ok(result_df
        .column(&config.alias_name)?
        .as_materialized_series()
        .clone())
}

pub struct RmaIndicator;

impl Indicator for RmaIndicator {
    fn calculate(
        &self,
        ohlcv_df: &DataFrame,
        indicator_key: &str,
        param_map: &HashMap<String, Param>,
    ) -> Result<Vec<Series>, QuantError> {
        let period = param_map
            .get("period")
            .map(|p| p.value as i64)
            .ok_or_else(|| {
                IndicatorError::InvalidParameter(
                    indicator_key.to_string(),
                    "Missing or invalid 'period' parameter".to_string(),
                )
            })?;

        let mut config = RMAConfig::new(period);
        config.alias_name = indicator_key.to_string();

        let result_series = rma_eager(ohlcv_df, &config)?;

        Ok(vec![result_series])
    }
}
