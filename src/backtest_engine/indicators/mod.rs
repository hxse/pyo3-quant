// src/backtest_engine/indicators/mod.rs
pub mod adx;
pub mod atr;
pub mod bbands;
mod calculator;
pub mod ema;
pub mod macd;
pub mod psar;
pub mod rma;
pub mod rsi;
pub mod sma;
pub mod tr;

use crate::data_conversion::{input::param_set::IndicatorsParams, DataContainer};
use crate::error::QuantError;
use polars::prelude::*;
use pyo3::{prelude::*, types::PyAny};
use pyo3_polars::PyDataFrame;
use std::collections::HashMap;

/// 计算多周期指标
/// 对每个数据源的每个周期分别计算指标,返回 HashMap<String, Vec<DataFrame>>
pub fn calculate_indicators(
    processed_data: &DataContainer,
    indicators_params: &IndicatorsParams,
) -> Result<HashMap<String, Vec<DataFrame>>, QuantError> {
    let mut all_indicators: HashMap<String, Vec<DataFrame>> = HashMap::new();

    for (source_name, mtf_indicator_params) in indicators_params.iter() {
        let source_data = processed_data.source.get(source_name).ok_or_else(|| {
            QuantError::InfrastructureError(format!("数据源 {} 未找到", source_name))
        })?;

        if source_data.len() != mtf_indicator_params.len() {
            return Err(QuantError::InfrastructureError(format!(
                "数据源 {} 的长度与指标参数长度不匹配: {} vs {}",
                source_name,
                source_data.len(),
                mtf_indicator_params.len()
            )));
        }

        let indicators_for_source = source_data
            .iter()
            .zip(mtf_indicator_params.iter())
            .map(|(data_df, mtf_params)| {
                calculator::calculate_single_period_indicators(data_df, mtf_params)
            })
            .collect::<Result<Vec<_>, QuantError>>()?;

        all_indicators.insert(source_name.clone(), indicators_for_source);
    }

    Ok(all_indicators)
}

#[pyfunction]
pub fn py_calculate_indicators(
    processed_data_py: &Bound<'_, PyAny>,
    indicators_params_py: &Bound<'_, PyAny>,
) -> PyResult<HashMap<String, Vec<PyDataFrame>>> {
    let processed_data: DataContainer = processed_data_py.extract()?;
    let indicators_params: IndicatorsParams = indicators_params_py.extract()?;

    let result_map = calculate_indicators(&processed_data, &indicators_params)?;

    let py_result_map: HashMap<String, Vec<PyDataFrame>> = result_map
        .into_iter()
        .map(|(k, v)| (k, v.into_iter().map(PyDataFrame).collect()))
        .collect();

    Ok(py_result_map)
}
