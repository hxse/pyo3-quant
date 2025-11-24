//! 数据转换模块
//!
//! 负责 Python 和 Rust 之间的数据转换:
//! - types: 输入参数和输出结果的类型定义
//! - utils: 辅助工具函数

pub mod types;
pub mod utils;

// 重新导出常用类型
use pyo3::prelude::*;

pub use types::{
    BacktestParams, DataContainer, ParamContainer, SettingContainer, SingleParam, TemplateContainer,
};

pub fn register_py_module(_m: &Bound<'_, PyModule>) -> PyResult<()> {
    // 目前没有直接从该模块导出的函数，函数体可以暂时只包含 `Ok(())`
    Ok(())
}
