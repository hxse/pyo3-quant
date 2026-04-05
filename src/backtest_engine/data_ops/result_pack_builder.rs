use crate::error::QuantError;
use crate::types::{DataPack, IndicatorResults, PerformanceMetrics, ResultPack, SourceRange};
use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::PyDataFrame;
use pyo3_stub_gen::derive::*;
use std::collections::HashMap;

fn attach_indicator_time_columns(
    data: &DataPack,
    indicators: Option<IndicatorResults>,
) -> Result<Option<IndicatorResults>, QuantError> {
    let Some(indicators) = indicators else {
        return Ok(None);
    };

    let mut normalized = HashMap::new();
    for (source_key, indicator_df) in indicators {
        if indicator_df
            .get_column_names()
            .iter()
            .any(|name| name.as_str() == "time")
        {
            return Err(QuantError::InvalidParam(format!(
                "indicators['{source_key}'] 不允许预先携带 time 列"
            )));
        }

        let source_df = data.source.get(&source_key).ok_or_else(|| {
            QuantError::InvalidParam(format!(
                "indicators['{source_key}'] 对应的 source 不存在于 DataPack"
            ))
        })?;
        if indicator_df.height() != source_df.height() {
            return Err(QuantError::InvalidParam(format!(
                "indicators['{source_key}'].height()={} 必须等于 data.source['{source_key}'].height()={}",
                indicator_df.height(),
                source_df.height()
            )));
        }

        let mut columns = Vec::with_capacity(indicator_df.width() + 1);
        columns.push(source_df.column("time")?.clone());
        columns.extend(indicator_df.get_columns().iter().cloned());
        let normalized_df = DataFrame::new(columns)?;
        normalized.insert(source_key, normalized_df);
    }

    Ok(Some(normalized))
}

pub fn strip_indicator_time_columns(
    indicators_with_time: &IndicatorResults,
) -> Result<IndicatorResults, QuantError> {
    let mut stripped = HashMap::new();
    for (source_key, indicator_df) in indicators_with_time {
        let time_count = indicator_df
            .get_column_names()
            .iter()
            .filter(|name| name.as_str() == "time")
            .count();
        if time_count == 0 {
            return Err(QuantError::InvalidParam(format!(
                "indicators['{source_key}'] 缺少 time 列，不能降级为 raw indicators"
            )));
        }
        if time_count > 1 {
            return Err(QuantError::InvalidParam(format!(
                "indicators['{source_key}'] 存在多个 time 列，不能降级"
            )));
        }
        let mut df = indicator_df.clone();
        df.drop_in_place("time")?;
        stripped.insert(source_key.clone(), df);
    }
    Ok(stripped)
}

fn build_result_mapping(
    data: &DataPack,
    indicator_source_keys: &[String],
) -> Result<DataFrame, QuantError> {
    let mut columns = Vec::with_capacity(indicator_source_keys.len() + 1);
    columns.push(data.mapping.column("time")?.clone());
    for source_key in indicator_source_keys {
        columns.push(data.mapping.column(source_key)?.clone());
    }
    Ok(DataFrame::new(columns)?)
}

fn build_result_ranges(
    data: &DataPack,
    indicator_source_keys: &[String],
) -> Result<HashMap<String, SourceRange>, QuantError> {
    let mut ranges = HashMap::new();
    let base_range = data.ranges.get(&data.base_data_key).ok_or_else(|| {
        QuantError::InvalidParam(format!(
            "DataPack.ranges 缺少 base_data_key='{}'",
            data.base_data_key
        ))
    })?;
    ranges.insert(data.base_data_key.clone(), base_range.clone());
    for source_key in indicator_source_keys {
        let range = data.ranges.get(source_key).ok_or_else(|| {
            QuantError::InvalidParam(format!(
                "DataPack.ranges 缺少 indicators source '{source_key}'"
            ))
        })?;
        ranges.insert(source_key.clone(), range.clone());
    }
    Ok(ranges)
}

fn strip_internal_backtest_columns(
    backtest: Option<DataFrame>,
) -> Result<Option<DataFrame>, QuantError> {
    let Some(mut df) = backtest else {
        return Ok(None);
    };
    if df
        .get_column_names()
        .iter()
        .any(|name| name.as_str() == "has_leading_nan")
    {
        df.drop_in_place("has_leading_nan")?;
    }
    Ok(Some(df))
}

pub fn build_result_pack(
    data: &DataPack,
    indicators: Option<IndicatorResults>,
    signals: Option<DataFrame>,
    backtest: Option<DataFrame>,
    performance: Option<PerformanceMetrics>,
) -> Result<ResultPack, QuantError> {
    let indicator_source_keys = {
        let mut keys = indicators
            .as_ref()
            .map(|map| map.keys().cloned().collect::<Vec<_>>())
            .unwrap_or_default();
        keys.sort_unstable();
        keys
    };

    let mapping_height = data.mapping.height();
    if let Some(signals_df) = &signals {
        if signals_df.height() != mapping_height {
            return Err(QuantError::InvalidParam(format!(
                "signals.height()={} 必须等于 data.mapping.height()={}",
                signals_df.height(),
                mapping_height
            )));
        }
    }
    if let Some(backtest_df) = &backtest {
        if backtest_df.height() != mapping_height {
            return Err(QuantError::InvalidParam(format!(
                "backtest.height()={} 必须等于 data.mapping.height()={}",
                backtest_df.height(),
                mapping_height
            )));
        }
    }

    let indicators_with_time = attach_indicator_time_columns(data, indicators)?;
    let public_backtest = strip_internal_backtest_columns(backtest)?;
    let mapping = build_result_mapping(data, &indicator_source_keys)?;
    let ranges = build_result_ranges(data, &indicator_source_keys)?;

    Ok(ResultPack::new_checked(
        indicators_with_time,
        signals,
        public_backtest,
        performance,
        mapping,
        ranges,
        data.base_data_key.clone(),
    ))
}

#[gen_stub_pyfunction(
    module = "pyo3_quant.backtest_engine.data_ops",
    python = r#"
import pyo3_quant

def build_result_pack(
    data: pyo3_quant.DataPack,
    indicators = None,
    signals = None,
    backtest_result = None,
    performance = None,
) -> pyo3_quant.ResultPack:
    """按统一 contract 构建 ResultPack"""
"#
)]
#[pyfunction(name = "build_result_pack")]
#[pyo3(signature = (data, indicators=None, signals=None, backtest_result=None, performance=None))]
pub fn py_build_result_pack(
    _py: Python<'_>,
    data: DataPack,
    indicators: Option<HashMap<String, Bound<'_, PyAny>>>,
    signals: Option<Bound<'_, PyAny>>,
    backtest_result: Option<Bound<'_, PyAny>>,
    performance: Option<PerformanceMetrics>,
) -> PyResult<ResultPack> {
    let indicators_inner = match indicators {
        Some(map) => {
            let mut inner = HashMap::new();
            for (key, value) in map {
                let df: PyDataFrame = value.extract()?;
                inner.insert(key, df.into());
            }
            Some(inner)
        }
        None => None,
    };
    let signals_inner = match signals {
        Some(value) => {
            let df: PyDataFrame = value.extract()?;
            Some(df.into())
        }
        None => None,
    };
    let backtest_inner = match backtest_result {
        Some(value) => {
            let df: PyDataFrame = value.extract()?;
            Some(df.into())
        }
        None => None,
    };

    build_result_pack(
        &data,
        indicators_inner,
        signals_inner,
        backtest_inner,
        performance,
    )
    .map_err(Into::into)
}

#[gen_stub_pyfunction(
    module = "pyo3_quant.backtest_engine.data_ops",
    python = r#"
import pyo3_quant

def strip_indicator_time_columns(
    indicators_with_time: dict[str, object],
) -> dict[str, object]:
    """把 ResultPack.indicators 降级回 raw indicators"""
"#
)]
#[pyfunction(name = "strip_indicator_time_columns")]
pub fn py_strip_indicator_time_columns(
    py: Python<'_>,
    indicators_with_time: HashMap<String, Bound<'_, PyAny>>,
) -> PyResult<HashMap<String, Py<PyAny>>> {
    let mut indicators_inner = HashMap::new();
    for (key, value) in indicators_with_time {
        let df: PyDataFrame = value.extract()?;
        indicators_inner.insert(key, df.into());
    }

    let stripped = strip_indicator_time_columns(&indicators_inner)?;
    let mut py_map = HashMap::new();
    for (key, value) in stripped {
        py_map.insert(
            key,
            PyDataFrame(value).into_pyobject(py)?.into_any().unbind(),
        );
    }
    Ok(py_map)
}

pub fn register_py_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(py_build_result_pack, m)?)?;
    m.add_function(wrap_pyfunction!(py_strip_indicator_time_columns, m)?)?;
    Ok(())
}
