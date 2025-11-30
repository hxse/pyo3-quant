use crate::data_conversion::types::SingleParam;
use crate::data_conversion::{DataContainer, ParamContainer, SettingContainer, TemplateContainer};
use pyo3::{prelude::*, types::PyDict};

// PyO3 入口函数
#[pyfunction]
pub fn calculate_metrics(
    py: Python<'_>,
    data_dict: DataContainer,
    param_set: ParamContainer,
    template: TemplateContainer,
    config: SettingContainer,
) -> PyResult<PyObject> {
    // 计算
    let mut summaries = Vec::new();
    for single_param in &param_set {
        let summary = calculate_metrics_internal(&data_dict, single_param, &template, &config)?;
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
        .enter_long
        .as_ref() // Option<SignalGroup> -> Option<&SignalGroup>
        .map(|group| {
            // group 的类型是 &SignalGroup
            group.comparisons.len() + group.sub_groups.len()
        })
        .unwrap_or(0); // 如果 Option 是 None，则返回 0

    let mut summary = format!(
        "Strategy: indicators count={}, signal_templates={}",
        params.indicators.len(),
        enter_long_count
    );

    summary.push_str(&format!(
        ", backtest sl={}, tp={}",
        params
            .backtest
            .sl_pct
            .as_ref()
            .map(|p| p.value)
            .unwrap_or(0.0),
        params
            .backtest
            .tp_pct
            .as_ref()
            .map(|p| p.value)
            .unwrap_or(0.0)
    ));

    // 添加数据信息
    summary.push_str(&format!(
        ", data keys count={}, mapping rows={}",
        data.source.get("ohlcv").map_or(0, |df| df.height()),
        data.mapping.height()
    ));

    Ok(summary)
}
