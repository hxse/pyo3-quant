use crate::backtest_engine::indicators::registry::Indicator;
use crate::error::{IndicatorError, QuantError};
use crate::types::Param;
use polars::prelude::*;
use std::collections::HashMap;

use super::config::PSARConfig;
use super::pipeline::psar_eager;

pub struct PsarIndicator;

impl Indicator for PsarIndicator {
    fn calculate(
        &self,
        ohlcv_df: &DataFrame,
        indicator_key: &str,
        params: &HashMap<String, Param>,
    ) -> Result<Vec<Series>, QuantError> {
        let af0 = params
            .get("af0")
            .ok_or_else(|| {
                IndicatorError::ParameterNotFound("af0".to_string(), indicator_key.to_string())
            })?
            .value;
        let af_step = params
            .get("af_step")
            .ok_or_else(|| {
                IndicatorError::ParameterNotFound("af_step".to_string(), indicator_key.to_string())
            })?
            .value;
        let max_af = params
            .get("max_af")
            .ok_or_else(|| {
                IndicatorError::ParameterNotFound("max_af".to_string(), indicator_key.to_string())
            })?
            .value;

        let config = PSARConfig::new(af0, af_step, max_af);
        let result_df = psar_eager(ohlcv_df, &config)?;

        let psar_long_named = result_df
            .column(&config.psar_long_alias)
            .map_err(QuantError::from)?
            .as_materialized_series()
            .clone()
            .with_name(format!("{}_long", indicator_key).into());
        let psar_short_named = result_df
            .column(&config.psar_short_alias)
            .map_err(QuantError::from)?
            .as_materialized_series()
            .clone()
            .with_name(format!("{}_short", indicator_key).into());
        let psar_af_named = result_df
            .column(&config.psar_af_alias)
            .map_err(QuantError::from)?
            .as_materialized_series()
            .clone()
            .with_name(format!("{}_af", indicator_key).into());
        let psar_reversal_named = result_df
            .column(&config.psar_reversal_alias)
            .map_err(QuantError::from)?
            .as_materialized_series()
            .clone()
            .with_name(format!("{}_reversal", indicator_key).into());

        Ok(vec![
            psar_long_named,
            psar_short_named,
            psar_af_named,
            psar_reversal_named,
        ])
    }
}
