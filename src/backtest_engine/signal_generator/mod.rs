use crate::backtest_engine::utils::column_names::ColumnName;
use crate::backtest_engine::utils::get_data_length;
use crate::types::IndicatorResults;
use crate::types::SignalParams;
use crate::types::{SignalGroup, SignalTemplate};
use crate::types::DataContainer;
use crate::error::QuantError;

use pyo3::prelude::*;
use pyo3_polars::PyDataFrame;

use polars::prelude::*;
use std::collections::HashMap;
use std::ops::BitOr;

pub mod condition_evaluator;
pub mod group_processor;
pub mod operand_resolver;
pub mod parser;
pub mod types; // 新增：解析器内部类型定义

use group_processor::process_signal_group;

// 辅助函数：处理单个信号字段的逻辑
fn process_signal_field_helper(
    group: Option<&SignalGroup>,
    processed_data: &DataContainer,
    indicator_dfs: &IndicatorResults,
    signal_params: &SignalParams,
    target_series: &mut Series,
    total_nan_mask: &mut BooleanChunked,
) -> Result<(), QuantError> {
    if let Some(group) = group {
        let (group_result, group_mask) =
            process_signal_group(group, processed_data, indicator_dfs, signal_params)?;
        // 使用 bitor 操作合并结果，避免不必要的 clone
        let result_chunked = target_series.bool()? | &group_result;
        *target_series = result_chunked.into_series();

        // 合并 NaN 掩码到总掩码中
        *total_nan_mask = total_nan_mask.clone().bitor(group_mask);
    }
    Ok(())
}

pub fn generate_signals(
    processed_data: &DataContainer,
    indicator_dfs: &IndicatorResults,
    signal_params: &SignalParams,
    signal_template: &SignalTemplate,
) -> Result<DataFrame, QuantError> {
    // 从 processed_data.source 获取基础数据的长度
    let data_len = get_data_length(processed_data, "generate_signals")?;

    if data_len == 0 {
        return Err(QuantError::Signal(crate::error::SignalError::InvalidInput(
            "数据长度为0, 无法生成信号".to_string(),
        )));
    }

    let mut entry_long_series =
        BooleanChunked::full(ColumnName::EntryLong.as_pl_small_str(), false, data_len)
            .into_series();
    let mut exit_long_series =
        BooleanChunked::full(ColumnName::ExitLong.as_pl_small_str(), false, data_len).into_series();
    let mut entry_short_series =
        BooleanChunked::full(ColumnName::EntryShort.as_pl_small_str(), false, data_len)
            .into_series();
    let mut exit_short_series =
        BooleanChunked::full(ColumnName::ExitShort.as_pl_small_str(), false, data_len)
            .into_series();

    let mut total_nan_mask =
        BooleanChunked::full(ColumnName::HasLeadingNan.as_pl_small_str(), false, data_len);

    process_signal_field_helper(
        signal_template.entry_long.as_ref(),
        processed_data,
        indicator_dfs,
        signal_params,
        &mut entry_long_series,
        &mut total_nan_mask,
    )?;
    process_signal_field_helper(
        signal_template.exit_long.as_ref(),
        processed_data,
        indicator_dfs,
        signal_params,
        &mut exit_long_series,
        &mut total_nan_mask,
    )?;
    process_signal_field_helper(
        signal_template.entry_short.as_ref(),
        processed_data,
        indicator_dfs,
        signal_params,
        &mut entry_short_series,
        &mut total_nan_mask,
    )?;
    process_signal_field_helper(
        signal_template.exit_short.as_ref(),
        processed_data,
        indicator_dfs,
        signal_params,
        &mut exit_short_series,
        &mut total_nan_mask,
    )?;

    let signals_df = DataFrame::new(vec![
        entry_long_series.into_column(),
        exit_long_series.into_column(),
        entry_short_series.into_column(),
        exit_short_series.into_column(),
        total_nan_mask.into_series().into_column(),
    ])?;

    Ok(signals_df)
}

#[pyfunction(name = "generate_signals")]
pub fn py_generate_signals(
    processed_data: DataContainer,
    indicator_dfs_py: HashMap<String, PyDataFrame>,
    signal_params: SignalParams,
    signal_template: SignalTemplate,
) -> PyResult<PyDataFrame> {
    // 1. 将 Python 对象转换为 Rust 类型
    let indicator_dfs = indicator_dfs_py
        .into_iter()
        .map(|(k, v)| (k, v.into()))
        .collect();

    // 2. 调用原始的 generate_signals 函数
    let result_df = generate_signals(
        &processed_data,
        &indicator_dfs,
        &signal_params,
        &signal_template,
    )?;

    // 3. 将返回的 Rust DataFrame 转换为 PyDataFrame
    Ok(PyDataFrame(result_df))
}
