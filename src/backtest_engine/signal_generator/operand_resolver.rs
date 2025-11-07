use crate::error::{QuantError, SignalError};

use crate::data_conversion::input::param_set::SignalParams;
use crate::data_conversion::input::template::{
    ParamOperand, SignalDataOperand, SignalRightOperand,
};

use crate::data_conversion::input::{DataContainer, DataSource};
use crate::data_conversion::output::IndicatorResults;
use polars::prelude::*;

/// 辅助函数：尝试从给定的数据源中解析 &Series
fn try_resolve_series<'a>(
    operand: &SignalDataOperand,
    data_source: &'a DataSource,
) -> Result<&'a Series, SignalError> {
    // 从 operand.source (例如 "ohlcv_0") 中拆分出 source_name ("ohlcv") 和 source_idx (0)
    let parts: Vec<&str> = operand.source.splitn(2, '_').collect();
    if parts.len() < 2 {
        return Err(SignalError::InvalidSourceFormat(operand.source.clone()));
    }
    let source_name = parts[0];
    let source_idx_str = parts[1];
    let source_idx = source_idx_str
        .parse::<usize>()
        .map_err(|_| SignalError::InvalidSourceFormat(operand.source.clone()))?;

    let dfs_vec = data_source
        .get(source_name)
        .ok_or_else(|| SignalError::SourceNotFound(source_name.to_string()))?;

    let df = dfs_vec.get(source_idx).ok_or_else(|| {
        SignalError::SourceIndexOutOfBounds(format!(
            "source: {}, index: {}",
            source_name, source_idx
        ))
    })?;

    let series = df
        .column(&operand.name)
        .map_err(|_| SignalError::ColumnNotFound(operand.name.clone()))?;

    Ok(series.as_materialized_series())
}

/// 私有辅助函数：根据需要应用数据映射
fn apply_mapping_if_needed(
    series_to_map: &Series,
    operand: &SignalDataOperand,
    processed_data: &DataContainer,
) -> Result<Series, SignalError> {
    // 从 operand.source (例如 "ohlcv_0") 中拆分出 source_name ("ohlcv") 和 source_idx (0)
    let parts: Vec<&str> = operand.source.splitn(2, '_').collect();
    if parts.len() < 2 {
        return Err(SignalError::InvalidSourceFormat(operand.source.clone()).into());
    }
    let source_name = parts[0];
    let source_idx_str = parts[1];
    let source_idx = source_idx_str
        .parse::<usize>()
        .map_err(|_| SignalError::InvalidSourceFormat(operand.source.clone()))?;

    let key = format!("{}_{}", source_name, source_idx);

    if let Some(false) = processed_data.skip_mapping.get(&key) {
        // 执行映射逻辑
        let mapping_df = &processed_data.mapping;
        let index_series = mapping_df
            .column(&key)
            .map_err(|_| SignalError::MappingColumnNotFound(key.to_string()))?;

        let index_series_u32 = index_series.cast(&DataType::UInt32).map_err(|e| {
            SignalError::MappingCastError(format!(
                "Failed to cast from dtype '{}' to UInt32: {}",
                index_series.dtype(),
                e
            ))
        })?;

        // unwrap是安全的，因为我们刚刚成功地转换了类型
        let indices = index_series_u32.u32().unwrap();

        series_to_map
            .take(indices)
            .map_err(|e| SignalError::MappingApplyError(e.to_string()).into())
    } else {
        // 不需要映射，直接克隆并返回原始 Series
        Ok(series_to_map.clone())
    }
}

/// 从 DataContainer 或 indicator_dfs 中解析 SignalDataOperand 为 Series
pub fn resolve_data_operand(
    operand: &SignalDataOperand,
    processed_data: &DataContainer,
    indicator_dfs: &IndicatorResults,
) -> Result<Series, SignalError> {
    let mut res = try_resolve_series(operand, &processed_data.source);

    if let Err(SignalError::ColumnNotFound(_)) = &res {
        res = try_resolve_series(operand, indicator_dfs);
    }

    let series = res?;

    let shifted_series = series.shift(operand.offset as i64);
    apply_mapping_if_needed(&shifted_series, operand, processed_data)
}

/// 从 signal_params 中解析 ParamOperand 为 f64
pub fn resolve_param_operand(
    operand: &ParamOperand,
    signal_params: &SignalParams,
) -> Result<f64, SignalError> {
    let param = signal_params
        .get(&operand.name)
        .ok_or_else(|| SignalError::ParameterNotFound(operand.name.clone()))?;

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
    indicator_dfs: &IndicatorResults,
    signal_params: &SignalParams,
) -> Result<ResolvedOperand, QuantError> {
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
