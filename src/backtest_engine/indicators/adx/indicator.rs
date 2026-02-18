use super::super::registry::Indicator;
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
}
