use polars::prelude::*;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use pyo3_polars::PyDataFrame;
use rayon::prelude::*; // 添加这一行

// mod types; // 已移动到 data_conversion/output/types.rs
mod backtester;
mod indicator_calculator;
mod performance_analyzer;
mod risk_adjuster;
mod signal_generator;
mod utils;

pub use crate::data_conversion::output::BacktestSummary;

use crate::data_conversion::{
    process_all_params, ProcessedConfig, ProcessedDataDict, ProcessedParamSet, ProcessedTemplate,
};

/// 主入口函数:运行回测引擎
#[pyfunction]
pub fn run_backtest_engine(
    py: Python<'_>,
    data_dict: ProcessedDataDict,
    param_set: ProcessedParamSet,
    template: ProcessedTemplate,
    config: ProcessedConfig,
) -> PyResult<PyObject> {
    // 1. 处理所有参数
    let (processed_data, processed_params, processed_template, processed_config) =
        process_all_params(py, data_dict, param_set, template, config)?;

    // 2. 根据任务数选择执行策略
    let total_tasks = processed_params.params.len();

    let results: Vec<BacktestSummary> = if total_tasks == 1 {
        // 单任务：直接执行，不限制 Polars 并发
        processed_params
            .params
            .into_iter()
            .map(|single_param| {
                execute_single_backtest(
                    &processed_data,
                    &single_param,
                    &processed_template,
                    &processed_config,
                )
            })
            .collect::<Result<Vec<_>, _>>()
            .map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Backtest error: {}", e))
            })?
    } else {
        // 多任务：使用 Rayon 并行，限制每个任务的 Polars 为单线程
        processed_params
            .params
            .par_iter()
            .map(|single_param| {
                utils::process_param_in_single_thread(|| {
                    execute_single_backtest(
                        &processed_data,
                        single_param,
                        &processed_template,
                        &processed_config,
                    )
                })
            })
            .collect::<Result<Vec<_>, _>>()
            .map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Backtest error: {}", e))
            })?
    };

    // 3. 将results转换为Python字典列表
    let py_list = pyo3::types::PyList::empty(py);
    for summary in results {
        let py_dict = summary.into_pyobject(py)?;
        py_list.append(py_dict)?;
    }
    Ok(py_list.into())
}

/// 辅助函数:判断是否有风控模板
fn has_risk_template(template: &ProcessedTemplate) -> bool {
    // 占位实现:简单判断，检查 source 字段是否为空
    !template.risk.template.is_empty()
}
/// 执行单个回测任务
fn execute_single_backtest(
    processed_data: &crate::data_conversion::ProcessedDataDict,
    single_param: &crate::data_conversion::ProcessedSingleParam,
    processed_template: &ProcessedTemplate,
    processed_config: &crate::data_conversion::ProcessedConfig,
) -> PolarsResult<BacktestSummary> {
    // 2.1 计算指标
    let indicators_df =
        indicator_calculator::calculate_indicators(processed_data, &single_param.indicators)?;

    // 2.2 生成信号
    let signals_df = signal_generator::generate_signals(
        processed_data,
        &indicators_df,
        &single_param.signal,
        &processed_template.signal.template,
    )?;

    // 2.3 创建初始仓位Series
    let initial_position_series = risk_adjuster::create_initial_position_series(
        processed_data,
        single_param.backtest.position_pct.value,
    )?;

    // 2.4 第一次回测
    let mut result_df = backtester::run_backtest(
        processed_data,
        &signals_df,
        initial_position_series,
        &single_param.backtest,
    )?;

    // 2.5 风控判断并可能进行第二次回测
    if has_risk_template(processed_template) {
        let adjusted_position_series = risk_adjuster::adjust_position_by_risk(
            &single_param.backtest,
            &result_df,
            &processed_template.risk,
            &single_param.risk,
        )?;

        result_df = backtester::run_backtest(
            processed_data,
            &signals_df,
            adjusted_position_series,
            &single_param.backtest,
        )?;
    }

    // 2.6 绩效评估
    let performance =
        performance_analyzer::analyze_performance(&result_df, &single_param.performance)?;

    // 2.7 内存优化
    let (opt_indicators, opt_signals, opt_backtest, final_perf) = utils::optimize_memory_if_needed(
        processed_config,
        indicators_df,
        signals_df,
        result_df,
        performance,
    );

    Ok(BacktestSummary {
        performance: final_perf,
        indicators: opt_indicators.map(PyDataFrame),
        signals: opt_signals.map(PyDataFrame),
        backtest_result: opt_backtest.map(PyDataFrame),
    })
}
