//! 输入数据转换
//!
//! 将 Python 传入的参数转换为 Rust 结构体

use pyo3::prelude::*;

pub mod data_dict;
pub mod param;
pub mod param_set;
pub mod settings;
pub mod template;

pub use data_dict::DataContainer;
pub use param::Param;
pub use param_set::{
    BacktestParams, ParamContainer, PerformanceParams, RiskParams, SignalParams, SingleParam,
};
pub use settings::SettingContainer;
pub use template::{RiskTemplate, SignalTemplate, TemplateContainer};

pub fn process_all_params(
    _py: Python<'_>,
    data_dict: DataContainer,
    param_set: ParamContainer,
    template: TemplateContainer,
    settings: SettingContainer,
) -> PyResult<(
    DataContainer,
    ParamContainer,
    TemplateContainer,
    SettingContainer,
)> {
    Ok((data_dict, param_set, template, settings))
}
