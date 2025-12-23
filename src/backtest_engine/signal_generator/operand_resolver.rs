use crate::error::{QuantError, SignalError};

use super::types::{OffsetType, ParamOperand, SignalDataOperand, SignalRightOperand};
use crate::data_conversion::types::param_set::SignalParams;

use crate::data_conversion::types::backtest_summary::IndicatorResults;
use crate::data_conversion::types::{DataContainer, DataSource};
use polars::prelude::*;

/// 辅助函数：尝试从给定的数据源中解析 &Series
fn try_resolve_series<'a>(
    source_key: &str,
    column_name: &str,
    data_source: &'a DataSource,
) -> Result<&'a Series, SignalError> {
    // 直接使用 source_key 作为键查找 DataFrame
    let df = data_source
        .get(source_key)
        .ok_or_else(|| SignalError::SourceNotFound(source_key.to_string()))?;

    let series = df
        .column(column_name)
        .map_err(|_| SignalError::ColumnNotFound(column_name.to_string()))?;

    Ok(series.as_materialized_series())
}

/// 私有辅助函数：根据需要应用数据映射
fn apply_mapping_if_needed(
    series_to_map: &Series,
    source_key: &str,
    processed_data: &DataContainer,
) -> Result<Series, SignalError> {
    let key = source_key;

    if let Some(false) = processed_data.skip_mapping.get(key) {
        // 执行映射逻辑
        let mapping_df = &processed_data.mapping;
        let index_series = mapping_df
            .column(key)
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
            .map_err(|e| SignalError::MappingApplyError(e.to_string()))
    } else {
        // 不需要映射，直接克隆并返回原始 Series
        Ok(series_to_map.clone())
    }
}

/// 从 DataContainer 或 indicator_dfs 中解析 SignalDataOperand 为 Series List
pub fn resolve_data_operand(
    operand: &SignalDataOperand,
    processed_data: &DataContainer,
    indicator_dfs: &IndicatorResults,
) -> Result<Vec<Series>, SignalError> {
    // 解析数据源：如果 operand.source 为空，则使用 base_data_key
    let source_key = if operand.source.is_empty() {
        &processed_data.base_data_key
    } else {
        &operand.source
    };
    let column_name = &operand.name;

    let mut res = try_resolve_series(source_key, column_name, &processed_data.source);

    if let Err(SignalError::ColumnNotFound(_)) = &res {
        res = try_resolve_series(source_key, column_name, indicator_dfs);
    }

    let series = res?;

    let offsets: Vec<i64> = match &operand.offset {
        OffsetType::Single(val) => vec![*val as i64],
        OffsetType::RangeAnd(start, end) | OffsetType::RangeOr(start, end) => {
            (*start..=*end).map(|x| x as i64).collect()
        }
        OffsetType::ListAnd(list) | OffsetType::ListOr(list) => {
            list.iter().map(|&x| x as i64).collect()
        }
    };

    let mut result_series = Vec::with_capacity(offsets.len());

    for offset in offsets {
        let shifted_series = series.shift(offset);
        let mapped_series = apply_mapping_if_needed(&shifted_series, source_key, processed_data)?;
        result_series.push(mapped_series);
    }

    Ok(result_series)
}

/// 从 signal_params 中解析 ParamOperand 为 f64
pub fn resolve_param_operand(
    operand: &ParamOperand,
    signal_params: &SignalParams,
) -> Result<f64, SignalError> {
    let param_name = &operand.name;

    let param = signal_params
        .get(param_name)
        .ok_or_else(|| SignalError::ParameterNotFound(param_name.to_string()))?;

    Ok(param.value)
}

/// 解析 SignalRightOperand 为 Series 或 f64
#[derive(Debug)]
pub enum ResolvedOperand {
    Series(Vec<Series>),
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
        SignalRightOperand::Scalar(value) => Ok(ResolvedOperand::Scalar(*value)),
    }
}
