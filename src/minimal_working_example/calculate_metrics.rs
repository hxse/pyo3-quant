use crate::data_conversion::input::SingleParam;
use crate::data_conversion::{
    process_all_params, DataContainer, ParamContainer, SettingContainer, TemplateContainer,
};
use pyo3::prelude::*;
use pyo3::types::PyDict;

// PyO3 入口函数
#[pyfunction]
pub fn calculate_metrics(
    py: Python<'_>,
    data_dict: DataContainer,
    param_set: ParamContainer,
    template: TemplateContainer,
    config: SettingContainer,
) -> PyResult<PyObject> {
    // 调用统一的参数处理入口函数
    let (processed_data, processed_params, processed_template, processed_config) =
        process_all_params(py, data_dict, param_set, template, config)?;

    // 计算
    let mut summaries = Vec::new();
    for single_param in &processed_params {
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
    data: &DataContainer,
    params: &SingleParam,
    template: &TemplateContainer,
    config: &SettingContainer,
) -> PyResult<String> {
    if config.return_only_final {
        return Ok("Performance metrics calculated (placeholder)".to_string());
    }

    let enter_long_count = template
        .signal
        .enter_long // 从 template.signal.enter_long 改为 template.enter_long
        .as_ref() // Option<Vec<SignalGroup>> -> Option<&Vec<SignalGroup>>
        .map(|groups| {
            // groups 的类型是 &Vec<SignalGroup>
            groups
                .iter() // 迭代 Vec<SignalGroup> 中的每个 SignalGroup
                .map(|group| group.conditions.len()) // 对每个 group，获取其 conditions 的长度
                .sum::<usize>() // 将所有长度求和
        })
        .unwrap_or(0); // 如果 Option 是 None，则返回 0

    let mut summary = format!(
        "Strategy: indicators count={}, signal_templates={}",
        params.indicators.len(),
        enter_long_count
    );

    summary.push_str(&format!(
        ", backtest sl={}, tp={}",
        params.backtest.sl_pct.value, params.backtest.tp_pct.value
    ));

    // 添加数据信息
    summary.push_str(&format!(
        ", data keys count={}, mapping rows={}",
        data.source.get("ohlcv").map_or(0, |df| df.len()),
        data.mapping.height()
    ));

    Ok(summary)
}
