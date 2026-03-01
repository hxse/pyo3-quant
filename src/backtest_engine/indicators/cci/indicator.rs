use super::super::registry::{require_resolved_param, Indicator};
use super::config::CCIConfig;
use super::pipeline::cci_eager;
use crate::error::{IndicatorError, QuantError};
use crate::types::Param;
use polars::prelude::*;
use std::collections::HashMap;

pub struct CciIndicator;

impl Indicator for CciIndicator {
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

        let mut config = CCIConfig::new(period);
        config.alias_name = indicator_key.to_string();

        if let Some(constant) = params.get("constant") {
            config.constant = constant.value;
        }

        let series = cci_eager(ohlcv_df, &config)?;
        Ok(vec![series])
    }

    fn required_warmup_bars(
        &self,
        resolved_params: &HashMap<String, f64>,
    ) -> Result<usize, QuantError> {
        // CCI 滚动窗口前导空值为 period-1。
        let period = require_resolved_param(resolved_params, "period", "cci")? as i64;
        Ok(period.saturating_sub(1) as usize)
    }

    fn warmup_mode(&self) -> crate::backtest_engine::indicators::registry::WarmupMode {
        // 中文注释：CCI 非预热段不允许中间空值。
        crate::backtest_engine::indicators::registry::WarmupMode::Strict
    }
}
