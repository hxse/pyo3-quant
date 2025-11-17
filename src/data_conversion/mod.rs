//! 数据转换模块
//!
//! 负责 Python 和 Rust 之间的数据转换:
//! - input: Python → Rust 的输入参数转换
//! - output: Rust → Python 的结果数据转换

pub mod input;
pub mod output;
pub mod utils;

// 重新导出常用类型
use pyo3::prelude::*;

pub use input::{
    process_all_params, BacktestParams, DataContainer, ParamContainer, SettingContainer,
    SingleParam, TemplateContainer,
};
pub use output::IndicatorResults;

pub fn register_py_module(_m: &Bound<'_, PyModule>) -> PyResult<()> {
    // 目前没有直接从该模块导出的函数，函数体可以暂时只包含 `Ok(())`
    Ok(())
}
