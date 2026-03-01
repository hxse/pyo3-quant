use super::super::registry::{require_resolved_param, Indicator};
use super::config::ADXConfig;
use super::pipeline::adx_eager;
use crate::error::{IndicatorError, QuantError};
use crate::types::Param;
use polars::prelude::*;
use std::collections::HashMap;

pub struct AdxIndicator;

impl Indicator for AdxIndicator {
    fn calculate(
        &self,
        ohlcv_df: &DataFrame,
        indicator_key: &str,
        param_map: &HashMap<String, Param>,
    ) -> Result<Vec<Series>, QuantError> {
        let period = param_map
            .get("period")
            .map(|param| param.value as i64)
            .ok_or_else(|| {
                IndicatorError::InvalidParameter(
                    indicator_key.to_string(),
                    "Missing or invalid 'period' parameter".to_string(),
                )
            })?;

        let adxr_length = param_map
            .get("adxr_length")
            .map(|param| param.value as i64)
            .unwrap_or(2);

        let mut config = ADXConfig::new(period, adxr_length);
        config.adx_alias = format!("{}_adx", indicator_key);
        config.adxr_alias = format!("{}_adxr", indicator_key);
        config.plus_dm_alias = format!("{}_plus_dm", indicator_key);
        config.minus_dm_alias = format!("{}_minus_dm", indicator_key);

        let (adx_series, adxr_series, plus_dm_series, minus_dm_series) =
            adx_eager(ohlcv_df, &config)?;

        Ok(vec![
            adx_series,
            adxr_series,
            plus_dm_series,
            minus_dm_series,
        ])
    }

    fn required_warmup_bars(
        &self,
        resolved_params: &HashMap<String, f64>,
    ) -> Result<usize, QuantError> {
        // 中文注释：全列口径取 ADX 全部输出列前导空值最大值。
        // 这里与当前实现对齐：max_leading_nan = 2*period + adxr_length - 1。
        let period = require_resolved_param(resolved_params, "period", "adx")? as i64;
        let adxr_length = resolved_params
            .get("adxr_length")
            .copied()
            .unwrap_or(2.0) as i64;
        Ok((2 * period + adxr_length - 1).max(0) as usize)
    }

    fn warmup_mode(&self) -> crate::backtest_engine::indicators::registry::WarmupMode {
        // 中文注释：ADX 非预热段不允许中间空值。
        crate::backtest_engine::indicators::registry::WarmupMode::Strict
    }
}
