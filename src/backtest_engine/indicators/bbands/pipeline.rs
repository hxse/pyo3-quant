use polars::lazy::dsl::col;
use polars::prelude::*;

use super::config::BBandsConfig;
use super::expr::bbands_lazy;
use crate::error::{IndicatorError, QuantError};

/// Eager 封装：计算并返回五个结果列。
pub fn bbands_eager(
    ohlcv_df: &DataFrame,
    config: &BBandsConfig,
) -> Result<(Series, Series, Series, Series, Series), QuantError> {
    if config.period <= 0 {
        return Err(IndicatorError::InvalidParameter(
            "bbands".to_string(),
            "Period must be positive".to_string(),
        )
        .into());
    }

    let series_len = ohlcv_df.height();
    let n_periods = config.period as usize;
    if series_len < n_periods {
        return Err(IndicatorError::DataTooShort(
            "bbands".to_string(),
            config.period,
            series_len as i64,
        )
        .into());
    }

    let lazy_df = ohlcv_df.clone().lazy();
    let lazy_plan = bbands_lazy(lazy_df, config)?;

    let combined_df = lazy_plan
        .select([
            col(config.lower_band_alias.as_str()),
            col(config.middle_band_alias.as_str()),
            col(config.upper_band_alias.as_str()),
            col(config.bandwidth_alias.as_str()),
            col(config.percent_alias.as_str()),
        ])
        .collect()
        .map_err(QuantError::from)?;

    Ok((
        combined_df
            .column(config.lower_band_alias.as_str())
            .map_err(QuantError::from)?
            .as_materialized_series()
            .clone(),
        combined_df
            .column(config.middle_band_alias.as_str())
            .map_err(QuantError::from)?
            .as_materialized_series()
            .clone(),
        combined_df
            .column(config.upper_band_alias.as_str())
            .map_err(QuantError::from)?
            .as_materialized_series()
            .clone(),
        combined_df
            .column(config.bandwidth_alias.as_str())
            .map_err(QuantError::from)?
            .as_materialized_series()
            .clone(),
        combined_df
            .column(config.percent_alias.as_str())
            .map_err(QuantError::from)?
            .as_materialized_series()
            .clone(),
    ))
}
