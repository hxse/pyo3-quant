use super::super::registry::{require_resolved_param, Indicator};
use super::config::ERConfig;
use super::pipeline::er_eager;
use crate::error::{IndicatorError, QuantError};
use crate::types::Param;
use polars::prelude::*;
use std::collections::HashMap;

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

    fn required_warmup_bars(
        &self,
        resolved_params: &HashMap<String, f64>,
    ) -> Result<usize, QuantError> {
        // ER 以 length 作为最小预热需求。
        let length = require_resolved_param(resolved_params, "length", "er")? as i64;
        Ok(length.max(0) as usize)
    }

    fn warmup_mode(&self) -> crate::backtest_engine::indicators::registry::WarmupMode {
        // 中文注释：ER 非预热段不允许中间空值。
        crate::backtest_engine::indicators::registry::WarmupMode::Strict
    }
}
