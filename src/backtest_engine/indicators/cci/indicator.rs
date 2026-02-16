use super::config::CCIConfig;
use super::pipeline::cci_eager;
use super::super::registry::Indicator;
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
}
