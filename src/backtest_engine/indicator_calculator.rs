use super::indicators::calculate_single_period_indicators;
use crate::data_conversion::{input::param_set::IndicatorsParams, ProcessedDataDict};
use polars::prelude::*;
use pyo3::{exceptions::PyRuntimeError, PyResult};

/// 计算多周期指标
/// 对 ohlcv 的每个周期分别计算指标,返回 Vec<DataFrame>
pub fn calculate_indicators(
    processed_data: &ProcessedDataDict,
    indicators_params: &IndicatorsParams,
) -> PyResult<Vec<DataFrame>> {
    if processed_data.ohlcv.len() != indicators_params.len() {
        return Err(PyRuntimeError::new_err(format!(
            "ohlcv 和 indicators_params 长度不匹配: {} vs {}",
            processed_data.ohlcv.len(),
            indicators_params.len()
        )));
    }

    processed_data
        .ohlcv
        .iter()
        .zip(indicators_params.iter())
        .map(|(ohlcv_df, mtf_params)| calculate_single_period_indicators(ohlcv_df, mtf_params))
        .collect::<PyResult<Vec<_>>>()
}
