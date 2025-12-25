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
//!
//! ### 单任务模式
//! - 直接顺序执行，不限制 Polars 的并发能力
//! - 适用于单个参数集的回测场景
//!
//! ### 多任务模式
//! - 使用 Rayon 进行任务级并行处理
//! - 通过 `utils::process_param_in_single_thread` 强制每个任务中的 Polars 使用单线程模式
//! - 避免了 Rayon 的任务并行与 Polars 的数据并行之间的冲突
//!
//! ## 执行阶段控制
//!
//! 回测过程分为四个可配置的执行阶段：
//! 1. **Indicator**: 技术指标计算阶段
//! 2. **Signals**: 交易信号生成阶段
//! 3. **Backtest**: 实际回测执行阶段
//! 4. **Performance**: 绩效分析阶段
//!
//! 通过 `ExecutionStage` 枚举控制执行到哪个阶段，支持部分执行和增量计算。
//!
//! ## 内存优化策略
//!
//! 在 `return_only_final` 模式下，系统会在每个阶段完成后立即释放不再需要的数据：
//! - 信号计算完成后释放指标数据
//! - 回测完成后释放信号数据
//! - 绩效计算完成后释放回测数据
//!
//! 这种策略显著降低了大规模回测的内存占用。

use pyo3::prelude::*;
use rayon::prelude::*;

// 子模块声明
pub mod backtester;
pub mod indicators;
mod performance_analyzer;
pub mod signal_generator;
mod utils;

// 重新导出常用类型
pub use crate::data_conversion::types::backtest_summary::BacktestSummary;

use crate::data_conversion::{
    DataContainer, ParamContainer, SettingContainer, SingleParam, TemplateContainer,
};
use crate::error::QuantError;

/// 纯 Rust 回测引擎主函数
///
/// 根据任务数量自动选择最优的执行策略：
/// - 单任务：直接执行，充分利用 Polars 的并发能力
/// - 多任务：使用 Rayon 并行，每个任务强制 Polars 单线程运行
///
/// # 参数
///
/// * `processed_data` - 预处理后的市场数据容器
/// * `processed_params` - 预处理后的回测参数集合
/// * `processed_template` - 预处理后的信号模板
/// * `processed_settings` - 预处理后的引擎设置
/// * `input_backtest_df` - 可选的输入回测结果，用于增量计算
///
/// # 返回值
///
/// 返回所有回测任务的摘要结果列表
///
/// # 性能考虑
///
/// 函数会记录并输出总执行时间，便于性能监控和优化
pub fn run_backtest_engine(
    processed_data: &DataContainer,
    processed_params: &Vec<SingleParam>,
    processed_template: &TemplateContainer,
    processed_settings: &SettingContainer,
    input_backtest_df: Option<BacktestSummary>,
) -> Result<Vec<BacktestSummary>, QuantError> {
    // 根据任务数选择执行策略
    let total_tasks = processed_params.len();

    let results: Vec<BacktestSummary> = if total_tasks == 1 {
        // 单任务：直接执行，不限制 Polars 并发
        // 这种情况下，Polars 可以充分利用其内部并行能力
        processed_params
            .iter()
            .map(|single_param| {
                execute_single_backtest(
                    processed_data,
                    single_param,
                    processed_template,
                    processed_settings,
                    // 注意：Polars 的 clone() 是浅拷贝，只增加引用计数，性能开销很小
                    input_backtest_df.clone(),
                )
            })
            .collect::<Result<Vec<_>, QuantError>>()?
    } else {
        // 多任务：使用 Rayon 并行，限制每个任务的 Polars 为单线程
        // 避免两层并行（Rayon 任务级 + Polars 数据级）的冲突
        processed_params
            .par_iter()
            .map(|single_param| {
                utils::process_param_in_single_thread(|| {
                    execute_single_backtest(
                        processed_data,
                        single_param,
                        processed_template,
                        processed_settings,
                        // 注意：Polars 的 clone() 是浅拷贝，只增加引用计数，性能开销很小
                        input_backtest_df.clone(),
                    )
                })
            })
            .collect::<Result<Vec<_>, QuantError>>()?
    };

    Ok(results)
}

/// 执行单个回测任务的核心函数
///
/// 按照执行阶段依次处理：
/// 1. 计算技术指标
/// 2. 生成交易信号
/// 3. 执行回测模拟
/// 4. 分析绩效结果
///
/// 支持增量计算：如果某个阶段已有结果，则跳过该阶段
///
/// # 内存管理
///
/// 在 `return_only_final` 模式下，会在每个阶段完成后立即释放不再需要的数据，
/// 以最小化内存占用。
///
/// # 参数
///
/// * `processed_data` - 市场数据
/// * `single_param` - 单个回测参数集
/// * `processed_template` - 信号模板
/// * `processed_settings` - 引擎设置
/// * `input_backtest_df` - 可选的已有回测结果
fn execute_single_backtest(
    processed_data: &DataContainer,
    single_param: &SingleParam,
    processed_template: &TemplateContainer,
    processed_settings: &SettingContainer,
    input_backtest_df: Option<BacktestSummary>,
) -> Result<BacktestSummary, QuantError> {
    // 1. 初始化执行上下文（支持增量计算）
    let mut ctx = utils::BacktestContext::from_cache(input_backtest_df);
    let stage = processed_settings.execution_stage;
    let return_only_final = processed_settings.return_only_final;

    // 2. 顺序执行各个阶段（每个方法内部处理 ExecutionStage 判断和缓存逻辑）
    ctx.execute_indicator_if_needed(stage, processed_data, &single_param.indicators)?;

    ctx.execute_signals_if_needed(
        stage,
        return_only_final,
        processed_data,
        &single_param.signal,
        &processed_template.signal,
    )?;

    ctx.execute_backtest_if_needed(
        stage,
        return_only_final,
        processed_data,
        &single_param.backtest,
    )?;

    ctx.execute_performance_if_needed(
        stage,
        return_only_final,
        processed_data,
        &single_param.performance,
    )?;

    // 3. 转换为最终结果
    Ok(ctx.into_summary(return_only_final, stage))
}

/// PyO3 接口函数：运行回测引擎
///
/// 这是 Python 端调用的入口函数，负责：
/// 1. 接收 Python 传递的参数
/// 2. 调用纯 Rust 回测引擎
/// 3. 将 Rust 结果转换为 Python 对象
///
/// # PyO3 参数说明
///
/// * `py` - Python GIL 锁定标记
/// * `data_dict` - 市场数据字典（Python → Rust 自动转换）
/// * `param_set` - 回测参数集合
/// * `template` - 信号生成模板
/// * `engine_settings` - 引擎配置设置
/// * `input_backtest_df` - 可选的已有回测结果
///
/// # 返回值
///
/// 返回 Python 列表，每个元素为一个回测摘要字典
#[pyfunction(name = "run_backtest_engine")]
pub fn py_run_backtest_engine(
    data_dict: DataContainer,
    param_set: ParamContainer,
    template: TemplateContainer,
    engine_settings: SettingContainer,
    input_backtest_df: Option<BacktestSummary>,
) -> PyResult<Vec<BacktestSummary>> {
    // 1. 调用纯 Rust 函数执行回测
    let results = run_backtest_engine(
        &data_dict,
        &param_set,
        &template,
        &engine_settings,
        input_backtest_df,
    )?;

    Ok(results)
}

/// 注册 PyO3 模块的所有函数
///
/// 这个函数将回测引擎的所有公共接口暴露给 Python 端，
/// 包括：
/// - 主回测引擎函数
/// - 各个独立模块的函数（指标计算、信号生成、回测执行、绩效分析）
///
/// # 参数
///
/// * `m` - PyO3 模块引用
///
/// # 返回值
///
/// 成功注册所有函数后返回 Ok(())，否则返回错误
pub fn register_py_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    // 注册主回测引擎函数
    m.add_function(wrap_pyfunction!(py_run_backtest_engine, m)?)?;

    // 注册各个子模块的函数
    m.add_function(wrap_pyfunction!(indicators::py_calculate_indicators, m)?)?;
    m.add_function(wrap_pyfunction!(signal_generator::py_generate_signals, m)?)?;
    m.add_function(wrap_pyfunction!(backtester::py_run_backtest, m)?)?;
    m.add_function(wrap_pyfunction!(
        performance_analyzer::py_analyze_performance,
        m
    )?)?;

    Ok(())
}
