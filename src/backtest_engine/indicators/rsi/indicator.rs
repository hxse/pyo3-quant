use super::config::RSIConfig;
use super::pipeline::rsi_eager;
use super::super::registry::Indicator;
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
}
