use super::config::SmaClosePctConfig;
use super::pipeline::sma_close_pct_eager;
use crate::backtest_engine::indicators::registry::Indicator;
use crate::error::{IndicatorError, QuantError};
use crate::types::Param;
use polars::prelude::*;
use std::collections::HashMap;

pub struct SmaClosePctIndicator;

impl Indicator for SmaClosePctIndicator {
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

        let mut config = SmaClosePctConfig::new(period);
        config.alias_name = indicator_key.to_string();

        let series = sma_close_pct_eager(ohlcv_df, &config)?;
        Ok(vec![series])
    }
}
