use crate::data_conversion::input::ProcessedSingleParam;
use crate::data_conversion::{
    process_all_params, ProcessedDataDict, ProcessedParamSet, ProcessedSettings, ProcessedTemplate,
};
use pyo3::prelude::*;
use pyo3::types::PyDict;

// PyO3 入口函数
#[pyfunction]
pub fn calculate_metrics(
    py: Python<'_>,
    data_dict: ProcessedDataDict,
    param_set: ProcessedParamSet,
    template: ProcessedTemplate,
    config: ProcessedSettings,
) -> PyResult<PyObject> {
    // 调用统一的参数处理入口函数
    let (processed_data, processed_params, processed_template, processed_config) =
        process_all_params(py, data_dict, param_set, template, config)?;

    // 计算
    let mut summaries = Vec::new();
    for single_param in &processed_params.params {
        let summary = calculate_metrics_internal(
            &processed_data,
            single_param,
            &processed_template,
            &processed_config,
        )?;
        summaries.push(summary);
    }

    // 返回结果
    let full_summary = summaries.join("\n");
    let py_dict = PyDict::new(py);
    py_dict.set_item("full_summary", full_summary)?;
    Ok(py_dict.unbind().into())
}

// 计算逻辑
fn calculate_metrics_internal(
    data: &ProcessedDataDict,
    params: &ProcessedSingleParam,
    template: &ProcessedTemplate,
    config: &ProcessedSettings,
) -> PyResult<String> {
    if config.return_only_final {
        return Ok("Performance metrics calculated (placeholder)".to_string());
    }

    let mut summary = format!(
        "Strategy: indicators count={}, signal_templates={}",
        params.indicators.len(),
        template.signal.template.len()
    );

    summary.push_str(&format!(
        ", backtest sl={}, tp={}",
        params.backtest.sl.value, params.backtest.tp.value
    ));

    // 添加数据信息
    summary.push_str(&format!(
        ", data keys count={}, mapping rows={}",
        data.ohlcv.len(),
        data.mapping.height()
    ));

    Ok(summary)
}
