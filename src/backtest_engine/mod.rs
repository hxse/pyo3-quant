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
//! - [`utils`]: 工具模块，提供并行调度与通用辅助能力
//!
//! ## 并行计算策略
//!
//! 回测引擎支持两种执行模式：
//! - 单任务模式：直接顺序执行，不限制 Polars 的并发能力
//! - 多任务模式：使用 Rayon 进行任务级并行处理，并在任务内限制 Polars 单线程
//!
//! ## 执行阶段控制
//!
//! 回测过程分为四个公开 stop 阶段：Indicator / Signals / Backtest / Performance。
//! 公开执行设置由 `SettingContainer { stop_stage, artifact_retention }` 表达，
//! 其中 `stop_stage` 决定停在哪一层，`artifact_retention` 决定公开结果保留哪些已完成阶段产物。

pub mod action_resolver;
pub mod backtester;
pub mod data_ops;
pub mod indicators;
pub mod optimizer;
mod pipeline;
mod performance_analyzer;
pub mod sensitivity;
pub mod signal_generator;
mod utils;
pub mod walk_forward;

mod module_registry;
mod submodule_init;
mod top_level_api;

pub use crate::types::ResultPack;
pub use module_registry::register_py_module;
pub(crate) use pipeline::{
    build_public_result_pack, compile_public_setting_to_request, evaluate_param_set,
    execute_single_pipeline, validate_mode_settings, PipelineOutput, PipelineRequest,
};
pub use top_level_api::{run_batch_backtest, run_single_backtest};
