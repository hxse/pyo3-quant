use super::super::registry::{require_resolved_param, Indicator};
use super::config::MACDConfig;
use super::pipeline::macd_eager;
use crate::error::{IndicatorError, QuantError};
use crate::types::Param;
use polars::prelude::*;
use std::collections::HashMap;

pub struct MacdIndicator;

impl Indicator for MacdIndicator {
    fn calculate(
        &self,
        ohlcv_df: &DataFrame,
        indicator_key: &str,
        param_map: &HashMap<String, Param>,
    ) -> Result<Vec<Series>, QuantError> {
        let fast_period = param_map
            .get("fast_period")
            .map(|param| param.value as i64)
            .ok_or_else(|| {
                IndicatorError::InvalidParameter(
                    indicator_key.to_string(),
                    "Missing or invalid 'fast_period' parameter".to_string(),
                )
            })?;

        let slow_period = param_map
            .get("slow_period")
            .map(|param| param.value as i64)
            .ok_or_else(|| {
                IndicatorError::InvalidParameter(
                    indicator_key.to_string(),
                    "Missing or invalid 'slow_period' parameter".to_string(),
                )
            })?;

        let signal_period = param_map
            .get("signal_period")
            .map(|param| param.value as i64)
            .ok_or_else(|| {
                IndicatorError::InvalidParameter(
                    indicator_key.to_string(),
                    "Missing or invalid 'signal_period' parameter".to_string(),
                )
            })?;

        let mut config = MACDConfig::new(fast_period, slow_period, signal_period);
        config.macd_alias = format!("{}_macd", indicator_key);
        config.signal_alias = format!("{}_signal", indicator_key);
        config.hist_alias = format!("{}_hist", indicator_key);

        let (macd_series, signal_series, hist_series) = macd_eager(ohlcv_df, &config)?;
        Ok(vec![macd_series, hist_series, signal_series])
    }

    fn required_warmup_bars(
        &self,
        resolved_params: &HashMap<String, f64>,
    ) -> Result<usize, QuantError> {
        // 与 expr 中 total_lookback 对齐：slow-1 + signal-1。
        let fast = require_resolved_param(resolved_params, "fast_period", "macd")? as i64;
        let slow = require_resolved_param(resolved_params, "slow_period", "macd")? as i64;
        let signal = require_resolved_param(resolved_params, "signal_period", "macd")? as i64;
        let max_period = fast.max(slow);
        Ok((max_period + signal - 2).max(0) as usize)
    }

    fn warmup_mode(&self) -> crate::backtest_engine::indicators::registry::WarmupMode {
        // 中文注释：MACD 非预热段不允许中间空值。
        crate::backtest_engine::indicators::registry::WarmupMode::Strict
    }
}
