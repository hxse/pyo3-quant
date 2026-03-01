use super::super::registry::{require_resolved_param, Indicator};
use super::config::ATRConfig;
use super::pipeline::atr_eager;
use crate::error::{IndicatorError, QuantError};
use crate::types::Param;
use polars::prelude::*;
use std::collections::HashMap;

pub struct AtrIndicator;

impl Indicator for AtrIndicator {
    fn calculate(
        &self,
        ohlcv_df: &DataFrame,
        indicator_key: &str,
        param_map: &HashMap<String, Param>,
    ) -> Result<Vec<Series>, QuantError> {
        let period = param_map
            .get("period")
            .map(|param| param.value)
            .ok_or_else(|| {
                IndicatorError::InvalidParameter(
                    indicator_key.to_string(),
                    "Missing or invalid 'period' parameter".to_string(),
                )
            })? as i64;

        let mut config = ATRConfig::new(period);
        config.alias_name = indicator_key.to_string();

        let atr_series = atr_eager(ohlcv_df, &config)?;
        Ok(vec![atr_series])
    }

    fn required_warmup_bars(
        &self,
        resolved_params: &HashMap<String, f64>,
    ) -> Result<usize, QuantError> {
        // ATR 当前实现在 index < period 置空。
        let period = require_resolved_param(resolved_params, "period", "atr")? as i64;
        Ok(period.max(0) as usize)
    }

    fn warmup_mode(&self) -> crate::backtest_engine::indicators::registry::WarmupMode {
        // 中文注释：ATR 非预热段不允许中间空值。
        crate::backtest_engine::indicators::registry::WarmupMode::Strict
    }
}
