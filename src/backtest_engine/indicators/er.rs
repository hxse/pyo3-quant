use super::registry::Indicator;
use super::utils::null_to_nan_expr;
use crate::error::{IndicatorError, QuantError};
use crate::types::Param;
use polars::lazy::dsl::col;
use polars::prelude::*;
use std::collections::HashMap;

/// ER (Efficiency Ratio) 配置结构体
pub struct ERConfig {
    pub length: i64,
    pub drift: i64,
    pub close_col: String,
    pub alias_name: String,
}

impl ERConfig {
    pub fn new(length: i64) -> Self {
        Self {
            length,
            drift: 1, // Default drift
            close_col: "close".to_string(),
            alias_name: "er".to_string(),
        }
    }
}

// --- 表达式层 ---

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

// --- 蓝图层 ---

pub fn er_lazy(lazy_df: LazyFrame, config: &ERConfig) -> Result<LazyFrame, QuantError> {
    let er_expr = er_expr(config)?;

    let result_lazy_df = lazy_df
        .with_column(er_expr)
        .with_column(null_to_nan_expr(&config.alias_name));

    Ok(result_lazy_df)
}

// --- 计算层 (Eager Wrapper) ---

pub fn er_eager(ohlcv_df: &DataFrame, config: &ERConfig) -> Result<Series, QuantError> {
    if config.length <= 0 {
        return Err(IndicatorError::InvalidParameter(
            "er".to_string(),
            "Length must be positive".to_string(),
        )
        .into());
    }

    if ohlcv_df.height() == 0 {
        return Ok(Series::new_empty(
            config.alias_name.as_str().into(),
            &DataType::Float64,
        ));
    }

    if ohlcv_df.height() < (config.length + 1) as usize {
        return Err(IndicatorError::DataTooShort(
            "er".to_string(),
            config.length + 1,
            ohlcv_df.height() as i64,
        )
        .into());
    }

    let lazy_df = ohlcv_df.clone().lazy();
    let lazy_plan = er_lazy(lazy_df, config)?;

    let df = lazy_plan
        .select([col(&config.alias_name)])
        .collect()
        .map_err(QuantError::from)?;

    Ok(df
        .column(&config.alias_name)?
        .as_materialized_series()
        .clone())
}

pub struct ErIndicator;

impl Indicator for ErIndicator {
    fn calculate(
        &self,
        ohlcv_df: &DataFrame,
        indicator_key: &str,
        params: &HashMap<String, Param>,
    ) -> Result<Vec<Series>, QuantError> {
        let length = params
            .get("length")
            .ok_or_else(|| {
                IndicatorError::ParameterNotFound("length".to_string(), indicator_key.to_string())
            })?
            .value as i64;

        let mut config = ERConfig::new(length);
        config.alias_name = indicator_key.to_string();

        if let Some(drift) = params.get("drift") {
            config.drift = drift.value as i64;
        }

        let series = er_eager(ohlcv_df, &config)?;
        Ok(vec![series])
    }
}
