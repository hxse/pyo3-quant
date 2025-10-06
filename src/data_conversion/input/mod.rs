//! 输入数据转换
//!
//! 将 Python 传入的参数转换为 Rust 结构体

use pyo3::prelude::*;
use pyo3::types::PyDict;
use pyo3::Bound;

pub mod config;
pub mod data_dict;
pub mod param;
pub mod param_set;
pub mod template;

pub use config::ProcessedConfig;
pub use data_dict::ProcessedDataDict;
pub use param::Param;
pub use param_set::{ProcessedParamSet, ProcessedSingleParam, BacktestParams, SignalParams, PerformanceParams};
pub use template::{ProcessedTemplate, SignalTemplate, RiskTemplate};

pub fn process_all_params(
    _py: Python<'_>,
    data_dict: Bound<'_, PyDict>,
    param_set: Vec<Bound<'_, PyDict>>,
    template: Bound<'_, PyDict>,
    config: Bound<'_, PyDict>,
) -> PyResult<(ProcessedDataDict, ProcessedParamSet, ProcessedTemplate, ProcessedConfig)> {
    // 调用各模块的 parse 函数
    let processed_data = data_dict::parse(data_dict)?;
    let processed_params = param_set::parse(param_set)?;
    let processed_template = template::parse(template)?;
    let processed_config = config::parse(config)?;

    Ok((processed_data, processed_params, processed_template, processed_config))
}
