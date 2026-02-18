use super::super::registry::Indicator;
use super::config::EMAConfig;
use super::pipeline::ema_eager;
use crate::error::{IndicatorError, QuantError};
use crate::types::Param;
use polars::prelude::*;
use std::collections::HashMap;

pub struct EmaIndicator;

impl Indicator for EmaIndicator {
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

        let mut config = EMAConfig::new(period);
        config.alias_name = indicator_key.to_string();
        let ema_series = ema_eager(ohlcv_df, &config)?;
        Ok(vec![ema_series])
    }
}
