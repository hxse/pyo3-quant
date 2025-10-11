//! 数据转换模块
//!
//! 负责 Python 和 Rust 之间的数据转换:
//! - input: Python → Rust 的输入参数转换
//! - output: Rust → Python 的结果数据转换

pub mod input;
pub mod output;

// 重新导出常用类型
pub use input::{
    process_all_params, BacktestParams, ProcessedDataDict, ProcessedParamSet, ProcessedSettings,
    ProcessedSingleParam, ProcessedTemplate, RiskTemplate, SignalParams, SignalTemplate,
};
pub use output::{BacktestSummary, PerformanceMetrics};
