use super::indicators::calculate_single_period_indicators;
use crate::data_conversion::{input::param_set::IndicatorsParams, DataContainer};
use polars::prelude::*;
use pyo3::{exceptions::PyRuntimeError, PyResult};
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
            .ok_or_else(|| PyRuntimeError::new_err(format!("数据源 {} 未找到", source_name)))?;

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
            .map(|(data_df, mtf_params)| calculate_single_period_indicators(data_df, mtf_params))
            .collect::<PyResult<Vec<_>>>()?;
        all_indicators.insert(source_name.clone(), indicators_for_source);
    }

    Ok(all_indicators)
}
