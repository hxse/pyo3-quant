use super::config::SmaClosePctConfig;
use super::pipeline::sma_close_pct_eager;
use crate::backtest_engine::indicators::registry::{require_resolved_param, Indicator};
use crate::error::{IndicatorError, QuantError};
use crate::types::Param;
use polars::prelude::*;
use std::collections::HashMap;

pub struct SmaClosePctIndicator;

impl Indicator for SmaClosePctIndicator {
    fn calculate(
        &self,
        ohlcv_df: &DataFrame,
        indicator_key: &str,
        params: &HashMap<String, Param>,
    ) -> Result<Vec<Series>, QuantError> {
        let period = params
            .get("period")
            .ok_or_else(|| {
                IndicatorError::ParameterNotFound("period".to_string(), indicator_key.to_string())
            })?
            .value as i64;

        let mut config = SmaClosePctConfig::new(period);
        config.alias_name = indicator_key.to_string();

        let series = sma_close_pct_eager(ohlcv_df, &config)?;
        Ok(vec![series])
    }

    fn required_warmup_bars(
        &self,
        resolved_params: &HashMap<String, f64>,
    ) -> Result<usize, QuantError> {
        // 底层依赖 SMA，预热与 SMA 一致。
        let period = require_resolved_param(resolved_params, "period", "sma-close-pct")? as i64;
        Ok(period.saturating_sub(1) as usize)
    }

    fn warmup_mode(&self) -> crate::backtest_engine::indicators::registry::WarmupMode {
        // 中文注释：sma-close-pct 非预热段不允许中间空值。
        crate::backtest_engine::indicators::registry::WarmupMode::Strict
    }
}
