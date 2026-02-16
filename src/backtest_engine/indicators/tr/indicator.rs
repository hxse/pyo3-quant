use super::config::TRConfig;
use super::pipeline::tr_eager;
use super::super::registry::Indicator;
use crate::error::QuantError;
use crate::types::Param;
use polars::prelude::*;
use std::collections::HashMap;

pub struct TrIndicator;

impl Indicator for TrIndicator {
    fn calculate(
        &self,
        ohlcv_df: &DataFrame,
        indicator_key: &str,
        _param_map: &HashMap<String, Param>,
    ) -> Result<Vec<Series>, QuantError> {
        let mut config = TRConfig::new();
        config.alias_name = indicator_key.to_string();

        let result_series = tr_eager(ohlcv_df, &config)?;
        Ok(vec![result_series])
    }
}
