//! # 回测引擎模块
//!
//! 这是整个量化回测系统的核心 Rust 模块，负责高性能的回测计算。
//!
//! ## 架构设计
//!
//! 本模块采用分层架构设计，包含以下核心组件：
//! - [`backtester`]: 回测执行引擎，负责实际的交易模拟
//! - [`indicators`]: 技术指标计算模块，提供各种技术分析指标
//! - [`signal_generator`]: 信号生成器，根据指标和模板生成交易信号
//! - [`performance_analyzer`]: 绩效分析器，计算回测结果的各种性能指标
//! - [`utils`]: 工具模块，提供内存优化和并行计算支持
//!
//! ## 并行计算策略
//!
//! 回测引擎支持两种执行模式：
//! - 单任务模式：直接顺序执行，不限制 Polars 的并发能力
//! - 多任务模式：使用 Rayon 进行任务级并行处理，并在任务内限制 Polars 单线程
//!
//! ## 执行阶段控制
//!
//! 回测过程分为四个可配置阶段：Indicator / Signals / Backtest / Performance。
//! 通过 `ExecutionStage` 控制执行到哪个阶段，支持部分执行和增量计算。

pub mod action_resolver;
pub mod backtester;
pub mod indicators;
pub mod optimizer;
mod performance_analyzer;
pub mod sensitivity;
pub mod signal_generator;
mod utils;
pub mod walk_forward;

mod module_registry;
mod submodule_init;
mod top_level_api;

pub use crate::types::BacktestSummary;
pub use module_registry::register_py_module;
pub(crate) use top_level_api::execute_single_backtest;
pub use top_level_api::run_backtest_engine;
