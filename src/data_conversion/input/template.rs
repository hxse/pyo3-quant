use pyo3::prelude::*;
use pyo3::types::{PyDict};
use pyo3::exceptions::PyKeyError;

#[derive(Debug)]
pub struct ProcessedTemplate {
    pub signal_templates: Vec<SignalTemplate>,
    pub risk_template: RiskTemplate,
}

#[derive(Clone, Debug, FromPyObject)]
#[pyo3(from_item_all)]
pub struct SignalTemplate {
    pub a: String,
    pub b: String,
    pub compare: String,
    pub col: String,
}

#[derive(Clone, Debug, FromPyObject)]
#[pyo3(from_item_all)]
pub struct RiskTemplate {
    pub method: String,
    pub source: String,
}



pub fn parse(template_dict: Bound<'_, PyDict>) -> PyResult<ProcessedTemplate> {
    // 解析 signal 模板
    let signal_list_any = template_dict
        .get_item("signal")?
        .ok_or_else(|| PyErr::new::<PyKeyError, _>("Missing 'signal' key"))?;
    let signal_list = signal_list_any.downcast::<pyo3::types::PyList>()?;
    let signal_templates = signal_list.extract()
        .map_err(|e| PyErr::new::<PyKeyError, _>(
            format!("Failed to parse signal templates: {}", e)
        ))?;

    // 解析 risk 模板
    let risk_dict_any = template_dict
        .get_item("risk")?
        .ok_or_else(|| PyErr::new::<PyKeyError, _>("Missing 'risk' key"))?;
    let risk_dict = risk_dict_any.downcast::<PyDict>()?;
    let risk_template = risk_dict.extract()
        .map_err(|e| PyErr::new::<PyKeyError, _>(
            format!("Failed to parse risk template: {}", e)
        ))?;

    Ok(ProcessedTemplate { signal_templates, risk_template })
}
