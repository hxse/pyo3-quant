use super::super::registry::Indicator;
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
}
