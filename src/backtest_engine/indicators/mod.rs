mod calculator;

pub mod adx;
pub mod atr;
pub mod bbands;
pub mod ema;
pub mod macd;
pub mod psar;
pub mod rma;
pub mod rsi;
pub mod sma;
pub mod tr;

use crate::data_conversion::{input::param_set::IndicatorsParams, DataContainer};
use polars::prelude::*;
use pyo3::{
    exceptions::{PyKeyError, PyRuntimeError},
    prelude::*,
    types::PyAny,
};
use pyo3_polars::PyDataFrame;
use std::collections::HashMap;

/// 计算多周期指标
/// 对每个数据源的每个周期分别计算指标,返回 HashMap<String, Vec<DataFrame>>
pub fn calculate_indicators(
    processed_data: &DataContainer,
    indicators_params: &IndicatorsParams,
) -> PyResult<HashMap<String, Vec<DataFrame>>> {
    let mut all_indicators: HashMap<String, Vec<DataFrame>> = HashMap::new();

    for (source_name, mtf_indicator_params) in indicators_params.iter() {
        let source_data = processed_data
            .source
            .get(source_name)
            .ok_or_else(|| PyKeyError::new_err(format!("数据源 {} 未找到", source_name)))?;

        if source_data.len() != mtf_indicator_params.len() {
            return Err(PyRuntimeError::new_err(format!(
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
            .collect::<PyResult<Vec<_>>>()?;
        all_indicators.insert(source_name.clone(), indicators_for_source);
    }

    Ok(all_indicators)
}

#[pyfunction]
pub fn py_calculate_indicators(
    processed_data_py: &Bound<'_, PyAny>,
    indicators_params_py: &Bound<'_, PyAny>,
) -> PyResult<HashMap<String, Vec<PyDataFrame>>> {
    // 1. 将 Python 对象转换为 Rust 类型
    let processed_data: DataContainer = processed_data_py.extract()?;
    let indicators_params: IndicatorsParams = indicators_params_py.extract()?;

    // 2. 调用原始的 calculate_indicators 函数，直接使用 '?' 传播 PyErr
    // 如果 calculate_indicators 失败，其内部的 PyErr 会被直接返回。
    let result_map = calculate_indicators(&processed_data, &indicators_params)?;

    // 3. 将返回的 Rust HashMap<String, Vec<DataFrame>> 转换为 HashMap<String, Vec<PyDataFrame>>
    let py_result_map: HashMap<String, Vec<PyDataFrame>> = result_map
        .into_iter()
        .map(|(k, v)| (k, v.into_iter().map(PyDataFrame).collect()))
        .collect();

    Ok(py_result_map)
}
