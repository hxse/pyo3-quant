//! 数据转换类型定义
//!
//! 将 Python 传入的参数转换为 Rust 结构体，并定义回测结果的类型

use pyo3::prelude::*;

pub mod backtest_summary;
pub mod data_dict;
pub mod param;
pub mod param_set;
pub mod settings;
pub mod templates;

pub use backtest_summary::{BacktestSummary, IndicatorResults, PerformanceMetrics};
pub use data_dict::{DataContainer, DataSource};
pub use param_set::{BacktestParams, ParamContainer, SingleParam};
pub use settings::SettingContainer;
pub use templates::TemplateContainer;
