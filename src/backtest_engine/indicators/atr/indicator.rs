use super::super::registry::Indicator;
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
}
