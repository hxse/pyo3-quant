use super::indicators::calculate_single_period_indicators;
use crate::data_conversion::{input::param_set::IndicatorsParams, ProcessedDataDict};
use polars::prelude::*;
use pyo3_polars::PyDataFrame;

/// 计算多周期指标
/// 对 ohlcv 的每个周期分别计算指标,返回 Vec<DataFrame>
pub fn calculate_indicators(
    processed_data: &ProcessedDataDict,
    indicators_params: &IndicatorsParams,
) -> PolarsResult<Vec<DataFrame>> {
    processed_data
        .ohlcv
        .iter()
        .map(|ohlcv_df: &PyDataFrame| {
            calculate_single_period_indicators(&ohlcv_df.0, indicators_params)
        })
        .collect::<PolarsResult<Vec<_>>>()
}
