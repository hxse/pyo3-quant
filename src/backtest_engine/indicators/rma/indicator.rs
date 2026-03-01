use super::super::registry::{require_resolved_param, Indicator};
use super::config::RMAConfig;
use super::pipeline::rma_eager;
use crate::error::{IndicatorError, QuantError};
use crate::types::Param;
use polars::prelude::*;
use std::collections::HashMap;

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

    fn required_warmup_bars(
        &self,
        resolved_params: &HashMap<String, f64>,
    ) -> Result<usize, QuantError> {
        // 独立 RMA 当前实现 ewm(min_periods=1)，不强制前导空值。
        let _ = require_resolved_param(resolved_params, "period", "rma")?;
        Ok(0)
    }

    fn warmup_mode(&self) -> crate::backtest_engine::indicators::registry::WarmupMode {
        // 中文注释：RMA 非预热段不允许中间空值。
        crate::backtest_engine::indicators::registry::WarmupMode::Strict
    }
}
