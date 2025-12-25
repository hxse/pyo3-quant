//! 数据转换模块
//!
//! 负责 Python 和 Rust 之间的数据转换:
//! - types: 输入参数和输出结果的类型定义
//! - utils: 辅助工具函数

pub mod types;
pub mod utils;

pub use types::{
    BacktestParams, DataContainer, IndicatorsParams, ParamContainer, PerformanceParams,
    SettingContainer, SignalParams, SingleParam, TemplateContainer,
};
