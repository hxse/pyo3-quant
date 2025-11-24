use crate::backtest_engine::indicators::{
    registry::Indicator,
    sma::{sma_eager, SMAConfig},
    utils::null_to_nan_expr,
};
use crate::data_conversion::types::param::Param;
use crate::error::{IndicatorError, QuantError};
use polars::lazy::dsl::{col, lit};
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
        let config = SMAConfig::new(period);

        let sma_series = sma_eager(ohlcv_df, &config)?;
        let sma_col_name = sma_series.name().to_string();

        let lazy_df = ohlcv_df
            .clone()
            .lazy()
            .with_column(lit(sma_series).alias(&sma_col_name));

        let pct_expr = ((col("close") - col(&sma_col_name)) / col(&sma_col_name)) * lit(100.0);

        let result_df = lazy_df
            .select(&[pct_expr.alias(indicator_key)])
            .with_columns(&[null_to_nan_expr(indicator_key)])
            .collect()
            .map_err(QuantError::from)?;

        let named_pct_series = result_df
            .column(indicator_key)?
            .as_materialized_series()
            .clone();

        Ok(vec![named_pct_series])
    }
}
