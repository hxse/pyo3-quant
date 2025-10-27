use crate::data_conversion::input::param_set::SignalParams;
use crate::data_conversion::input::template::{
    ParamOperand, SignalDataOperand, SignalRightOperand,
};
use crate::data_conversion::input::DataContainer;
use polars::prelude::*;
use pyo3::exceptions::{PyIndexError, PyKeyError, PyValueError};
use pyo3::prelude::*;
use std::collections::HashMap;

/// 自定义错误类型，用于操作数解析失败的情况
#[derive(Debug)]
enum OperandResolutionError {
    SourceNotFound(String),
    SourceIndexOutOfBounds { source: String, index: u32 },
    ColumnNotFound(String),
    InvalidSourceFormat(String),
}

/// 将 OperandResolutionError 转换为 PyErr 的辅助函数
fn to_py_err(e: OperandResolutionError) -> PyErr {
    match e {
        OperandResolutionError::SourceNotFound(s) => {
            PyKeyError::new_err(format!("Data source '{}' not found", s))
        }
        OperandResolutionError::SourceIndexOutOfBounds { source, index } => PyIndexError::new_err(
            format!("Data at index {} not found for source '{}'", index, source),
        ),
        OperandResolutionError::ColumnNotFound(s) => {
            PyKeyError::new_err(format!("Column '{}' not found", s))
        }
        OperandResolutionError::InvalidSourceFormat(s) => PyValueError::new_err(format!(
            "Invalid source format: '{}'. Expected 'sourceName_index'",
            s
        )),
    }
}

/// 辅助函数：尝试从给定的数据源中解析 &Series
fn try_resolve_series<'a>(
    operand: &SignalDataOperand,
    data_source: &'a HashMap<String, Vec<DataFrame>>,
) -> Result<&'a Series, OperandResolutionError> {
    // 从 operand.source (例如 "ohlcv_0") 中拆分出 source_name ("ohlcv") 和 source_idx (0)
    let parts: Vec<&str> = operand.source.splitn(2, '_').collect();
    if parts.len() < 2 {
        return Err(OperandResolutionError::InvalidSourceFormat(
            operand.source.clone(),
        ));
    }
    let source_name = parts[0];
    let source_idx_str = parts[1];
    let source_idx = source_idx_str
        .parse::<usize>()
        .map_err(|_| OperandResolutionError::InvalidSourceFormat(operand.source.clone()))?;

    let dfs_vec = data_source
        .get(source_name)
        .ok_or_else(|| OperandResolutionError::SourceNotFound(source_name.to_string()))?;

    let df =
        dfs_vec
            .get(source_idx)
            .ok_or_else(|| OperandResolutionError::SourceIndexOutOfBounds {
                source: source_name.to_string(),
                index: source_idx as u32,
            })?;

    let series = df
        .column(&operand.name)
        .map_err(|_| OperandResolutionError::ColumnNotFound(operand.name.clone()))?;

    Ok(series.as_materialized_series())
}

/// 私有辅助函数：根据需要应用数据映射
fn apply_mapping_if_needed(
    series_to_map: &Series,
    operand: &SignalDataOperand,
    processed_data: &DataContainer,
) -> PyResult<Series> {
    // 从 operand.source (例如 "ohlcv_0") 中拆分出 source_name ("ohlcv") 和 source_idx (0)
    let parts: Vec<&str> = operand.source.splitn(2, '_').collect();
    if parts.len() < 2 {
        return Err(to_py_err(OperandResolutionError::InvalidSourceFormat(
            operand.source.clone(),
        )));
    }
    let source_name = parts[0];
    let source_idx_str = parts[1];
    let source_idx = source_idx_str.parse::<usize>().map_err(|_| {
        to_py_err(OperandResolutionError::InvalidSourceFormat(
            operand.source.clone(),
        ))
    })?;

    let key = format!("{}_{}", source_name, source_idx);

    if let Some(false) = processed_data.skip_mapping.get(&key) {
        // 执行映射逻辑
        let mapping_df = &processed_data.mapping;
        let index_series = mapping_df.column(&key).map_err(|_| {
            PyKeyError::new_err(format!("Mapping index column '{}' not found", key))
        })?;

        let index_series_u32 = index_series.cast(&DataType::UInt32).map_err(|e| {
            PyValueError::new_err(format!(
                "Failed to cast mapping index from dtype '{}' to UInt32: {}",
                index_series.dtype(),
                e
            ))
        })?;

        // unwrap是安全的，因为我们刚刚成功地转换了类型
        let indices = index_series_u32.u32().unwrap();

        series_to_map
            .take(indices)
            .map_err(|e| PyIndexError::new_err(format!("Failed to apply mapping to series: {}", e)))
    } else {
        // 不需要映射，直接克隆并返回原始 Series
        Ok(series_to_map.clone())
    }
}

/// 从 DataContainer 或 indicator_dfs 中解析 SignalDataOperand 为 Series
pub fn resolve_data_operand(
    operand: &SignalDataOperand,
    processed_data: &DataContainer,
    indicator_dfs: &HashMap<String, Vec<DataFrame>>,
) -> PyResult<Series> {
    let mut res = try_resolve_series(operand, &processed_data.source);

    if let Err(OperandResolutionError::ColumnNotFound(_)) = &res {
        res = try_resolve_series(operand, indicator_dfs);
    }

    match res {
        Ok(series) => {
            let shifted_series = series.shift(operand.offset as i64);
            apply_mapping_if_needed(&shifted_series, operand, processed_data)
        }
        Err(e) => Err(to_py_err(e)),
    }
}

/// 从 signal_params 中解析 ParamOperand 为 f64
pub fn resolve_param_operand(
    operand: &ParamOperand,
    signal_params: &SignalParams,
) -> PyResult<f64> {
    let param = signal_params.get(&operand.name).ok_or_else(|| {
        PyKeyError::new_err(format!(
            "Parameter '{}' not found in signal_params",
            operand.name
        ))
    })?;

    Ok(param.value)
}

/// 解析 SignalRightOperand 为 Series 或 f64
#[derive(Debug)]
pub enum ResolvedOperand {
    Series(Series),
    Scalar(f64),
}

pub fn resolve_right_operand(
    operand: &SignalRightOperand,
    processed_data: &DataContainer,
    indicator_dfs: &HashMap<String, Vec<DataFrame>>,
    signal_params: &SignalParams,
) -> PyResult<ResolvedOperand> {
    match operand {
        SignalRightOperand::Data(data_operand) => {
            let series = resolve_data_operand(data_operand, processed_data, indicator_dfs)?;
            Ok(ResolvedOperand::Series(series))
        }
        SignalRightOperand::Param(param_operand) => {
            let scalar = resolve_param_operand(param_operand, signal_params)?;
            Ok(ResolvedOperand::Scalar(scalar))
        }
    }
}
