use crate::backtest_engine::utils::column_names::ColumnName;
use crate::data_conversion::types::backtest_summary::IndicatorResults;
use crate::data_conversion::types::param_set::SignalParams;
use crate::data_conversion::types::templates::{SignalGroup, SignalTemplate};
use crate::data_conversion::types::DataContainer;
use crate::error::QuantError;

use pyo3::{prelude::*, types::PyAny};
use pyo3_polars::PyDataFrame;

use polars::prelude::*;
use std::collections::HashMap;

pub mod condition_evaluator;
pub mod group_processor;
pub mod operand_resolver;

pub use group_processor::*;

// 辅助函数：处理单个信号字段的逻辑
fn process_signal_field_helper(
    groups: Option<&Vec<SignalGroup>>,
    processed_data: &DataContainer,
    indicator_dfs: &IndicatorResults,
    signal_params: &SignalParams,
    target_series: &mut Series,
) -> Result<(), QuantError> {
    if let Some(groups) = groups {
        for group in groups {
            let group_result =
                process_signal_group(&group, processed_data, indicator_dfs, signal_params)?;
            // 克隆 target_series，然后进行bitor操作
            *target_series = (&*target_series | &group_result)?;
        }
    }
    Ok(())
}

pub fn generate_signals(
    processed_data: &DataContainer,
    indicator_dfs: &IndicatorResults,
    signal_params: &SignalParams,
    signal_template: &SignalTemplate,
) -> Result<DataFrame, QuantError> {
    // 从 processed_data.mapping 获取数据长度
    let data_len = processed_data.mapping.height();

    if data_len == 0 {
        return Err(QuantError::Signal(crate::error::SignalError::InvalidInput(
            "数据长度为0, 无法生成信号".to_string(),
        )));
    }

    let mut enter_long_series =
        BooleanChunked::full(ColumnName::EnterLong.as_pl_small_str(), false, data_len)
            .into_series();
    let mut exit_long_series =
        BooleanChunked::full(ColumnName::ExitLong.as_pl_small_str(), false, data_len).into_series();
    let mut enter_short_series =
        BooleanChunked::full(ColumnName::EnterShort.as_pl_small_str(), false, data_len)
            .into_series();
    let mut exit_short_series =
        BooleanChunked::full(ColumnName::ExitShort.as_pl_small_str(), false, data_len)
            .into_series();

    process_signal_field_helper(
        signal_template.enter_long.as_ref(),
        processed_data,
        indicator_dfs,
        signal_params,
        &mut enter_long_series,
    )?;
    process_signal_field_helper(
        signal_template.exit_long.as_ref(),
        processed_data,
        indicator_dfs,
        signal_params,
        &mut exit_long_series,
    )?;
    process_signal_field_helper(
        signal_template.enter_short.as_ref(),
        processed_data,
        indicator_dfs,
        signal_params,
        &mut enter_short_series,
    )?;
    process_signal_field_helper(
        signal_template.exit_short.as_ref(),
        processed_data,
        indicator_dfs,
        signal_params,
        &mut exit_short_series,
    )?;

    let signals_df = DataFrame::new(vec![
        enter_long_series.into_column(),
        exit_long_series.into_column(),
        enter_short_series.into_column(),
        exit_short_series.into_column(),
    ])?;

    Ok(signals_df)
}

#[pyfunction(name = "generate_signals")]
pub fn py_generate_signals(
    processed_data_py: &Bound<'_, PyAny>,
    indicator_dfs_py: &Bound<'_, PyAny>,
    signal_params_py: &Bound<'_, PyAny>,
    signal_template_py: &Bound<'_, PyAny>,
) -> PyResult<PyDataFrame> {
    // 1. 将 Python 对象转换为 Rust 类型
    let processed_data: DataContainer = processed_data_py.extract()?;

    let indicator_dfs_py_map: HashMap<String, Vec<PyDataFrame>> = indicator_dfs_py.extract()?;
    let indicator_dfs = indicator_dfs_py_map
        .into_iter()
        .map(|(k, v)| (k, v.into_iter().map(|df| df.into()).collect()))
        .collect();

    let signal_params: SignalParams = signal_params_py.extract()?;
    let signal_template: SignalTemplate = signal_template_py.extract()?;

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
