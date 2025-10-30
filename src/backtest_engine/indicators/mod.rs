// src/backtest_engine/indicators/mod.rs
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

pub mod extended;

pub mod registry;
use self::registry::get_indicator_registry;
use crate::data_conversion::{
    input::param::Param, input::param_set::IndicatorsParams, DataContainer,
};
use crate::error::{IndicatorError, QuantError};
use polars::prelude::*;
use pyo3::{prelude::*, types::PyAny};
use pyo3_polars::PyDataFrame;
use std::collections::HashMap;

/// 计算单个周期的指标 (已重构)
pub fn calculate_single_period_indicators(
    ohlcv_df: &DataFrame,
    period_params: &HashMap<String, HashMap<String, Param>>,
) -> Result<DataFrame, QuantError> {
    let registry = get_indicator_registry();
    let mut all_series: Vec<Series> = Vec::new();

    for (indicator_key, param_map) in period_params {
        let base_name = indicator_key.split('_').next().unwrap_or(indicator_key);

        let indicator = registry.get(base_name).ok_or_else(|| {
            IndicatorError::NotImplemented(format!("Indicator '{}' is not supported.", base_name))
        })?;

        let mut calculated_series = indicator.calculate(ohlcv_df, indicator_key, param_map)?;
        all_series.append(&mut calculated_series);
    }

    if all_series.is_empty() {
        Ok(DataFrame::empty())
    } else {
        let all_columns: Vec<Column> = all_series.into_iter().map(|s| s.into_column()).collect();
        DataFrame::new(all_columns).map_err(QuantError::Polars)
    }
}

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
            .map(|(data_df, mtf_params)| calculate_single_period_indicators(data_df, mtf_params))
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
