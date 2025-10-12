//! 输入数据转换
//!
//! 将 Python 传入的参数转换为 Rust 结构体

use pyo3::prelude::*;
use pyo3::types::PyDict;
use pyo3::Bound;

pub mod data_dict;
pub mod param;
pub mod param_set;
pub mod settings;
pub mod template;

pub use data_dict::ProcessedDataDict;
pub use param::Param;
pub use param_set::{
    BacktestParams, PerformanceParams, ProcessedParamSet, ProcessedSingleParam, RiskParams,
    SignalParams,
};
pub use settings::ProcessedSettings;
pub use template::{ProcessedTemplate, RiskTemplate, SignalTemplate};

pub fn process_all_params(
    _py: Python<'_>,
    data_dict: ProcessedDataDict,
    param_set: ProcessedParamSet,
    template: ProcessedTemplate,
    settings: ProcessedSettings,
) -> PyResult<(
    ProcessedDataDict,
    ProcessedParamSet,
    ProcessedTemplate,
    ProcessedSettings,
)> {
    Ok((data_dict, param_set, template, settings))
}
