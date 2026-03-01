use super::super::registry::{require_resolved_param, Indicator};
use super::config::RSIConfig;
use super::pipeline::rsi_eager;
use crate::error::{IndicatorError, QuantError};
use crate::types::Param;
use polars::prelude::*;
use std::collections::HashMap;

pub struct RsiIndicator;

impl Indicator for RsiIndicator {
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

        let mut config = RSIConfig::new(period);
        config.alias_name = indicator_key.to_string();

        let result_series = rsi_eager(ohlcv_df, &config)?;
        Ok(vec![result_series])
    }

    fn required_warmup_bars(
        &self,
        resolved_params: &HashMap<String, f64>,
    ) -> Result<usize, QuantError> {
        // RSI 预处理在 index < period 置空，首个有效位对应 period。
        let period = require_resolved_param(resolved_params, "period", "rsi")? as i64;
        Ok(period.max(0) as usize)
    }

    fn warmup_mode(&self) -> crate::backtest_engine::indicators::registry::WarmupMode {
        // 中文注释：RSI 非预热段不允许中间空值。
        crate::backtest_engine::indicators::registry::WarmupMode::Strict
    }
}
