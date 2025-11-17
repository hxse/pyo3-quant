//! 输入数据转换
//!
//! 将 Python 传入的参数转换为 Rust 结构体

use pyo3::prelude::*;

pub mod data_dict;
pub mod param;
pub mod param_set;
pub mod settings;
pub mod template;

pub use data_dict::{DataContainer, DataSource};
pub use param_set::{BacktestParams, ParamContainer, SingleParam};
pub use settings::SettingContainer;
pub use template::TemplateContainer;
