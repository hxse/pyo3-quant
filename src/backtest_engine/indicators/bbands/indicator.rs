use polars::prelude::*;
use std::collections::HashMap;

use super::super::registry::{require_resolved_param, Indicator};
use super::config::BBandsConfig;
use super::pipeline::bbands_eager;
use crate::error::{IndicatorError, QuantError};
use crate::types::Param;

pub struct BbandsIndicator;

impl Indicator for BbandsIndicator {
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
        let std_multiplier = params
            .get("std")
            .ok_or_else(|| {
                IndicatorError::ParameterNotFound("std".to_string(), indicator_key.to_string())
            })?
            .value;

        let mut config = BBandsConfig::new(period, std_multiplier);
        config.middle_band_alias = format!("{}_middle", indicator_key);
        config.std_dev_alias = format!("{}_std_dev", indicator_key);
        config.upper_band_alias = format!("{}_upper", indicator_key);
        config.lower_band_alias = format!("{}_lower", indicator_key);
        config.bandwidth_alias = format!("{}_bandwidth", indicator_key);
        config.percent_alias = format!("{}_percent", indicator_key);

        let (lower, middle, upper, bandwidth, percent) = bbands_eager(ohlcv_df, &config)?;
        Ok(vec![lower, middle, upper, bandwidth, percent])
    }

    fn required_warmup_bars(
        &self,
        resolved_params: &HashMap<String, f64>,
    ) -> Result<usize, QuantError> {
        // BBands 核心滚动窗口前导空值为 period-1。
        let period = require_resolved_param(resolved_params, "period", "bbands")? as i64;
        Ok(period.saturating_sub(1) as usize)
    }

    fn warmup_mode(&self) -> crate::backtest_engine::indicators::registry::WarmupMode {
        // 中文注释：BBands 非预热段不允许中间空值。
        crate::backtest_engine::indicators::registry::WarmupMode::Strict
    }
}
