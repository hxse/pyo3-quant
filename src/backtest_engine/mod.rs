use crate::data_conversion::input::settings::ExecutionStage;
use polars::prelude::*;
use pyo3::prelude::*;
use rayon::prelude::*;

mod backtester;
pub mod indicators;
mod performance_analyzer;
mod risk_adjuster;
pub mod signal_generator;
mod utils;

pub use crate::data_conversion::output::BacktestSummary;

use crate::data_conversion::{
    process_all_params, DataContainer, ParamContainer, SettingContainer, TemplateContainer,
};

/// 主入口函数:运行回测引擎
#[pyfunction]
pub fn run_backtest_engine(
    py: Python<'_>,
    data_dict: DataContainer,
    param_set: ParamContainer,
    template: TemplateContainer,
    engine_settings: SettingContainer,
) -> PyResult<PyObject> {
    // 1. 处理所有参数
    let (processed_data, processed_params, processed_template, processed_settings) =
        process_all_params(py, data_dict, param_set, template, engine_settings)?;

    // 2. 根据任务数选择执行策略
    let total_tasks = processed_params.len();

    let results: Vec<BacktestSummary> = if total_tasks == 1 {
        // 单任务：直接执行，不限制 Polars 并发
        processed_params
            .into_iter()
            .map(|single_param| {
                execute_single_backtest(
                    &processed_data,
                    &single_param,
                    &processed_template,
                    &processed_settings,
                )
            })
            .collect::<Result<Vec<_>, _>>()
            .map_err(|e| {
                PyErr::new::<pyo3::exceptions::PyRuntimeError, _>(format!("Backtest error: {}", e))
            })?
    } else {
        // 多任务：使用 Rayon 并行，限制每个任务的 Polars 为单线程
        processed_params
            .par_iter()
            .map(|single_param| {
                utils::process_param_in_single_thread(|| {
                    execute_single_backtest(
                        &processed_data,
                        single_param,
                        &processed_template,
                        &processed_settings,
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

/// 执行单个回测任务
fn execute_single_backtest(
    processed_data: &crate::data_conversion::DataContainer,
    single_param: &crate::data_conversion::SingleParam,
    processed_template: &TemplateContainer,
    processed_settings: &crate::data_conversion::SettingContainer,
) -> PolarsResult<BacktestSummary> {
    let mut indicator_dfs: Option<std::collections::HashMap<String, Vec<DataFrame>>> = None;
    let mut signals_df = None;
    let mut backtest_df = None;
    let mut performance = None;

    // 1. 始终执行: 计算指标
    let calculated_indicator_dfs =
        indicators::calculate_indicators(processed_data, &single_param.indicators)?;
    indicator_dfs = Some(calculated_indicator_dfs);

    // 2. 如果 execution_stage >= "signals": 执行信号生成
    if processed_settings.execution_stage >= ExecutionStage::Signals {
        if let Some(ref ind_dfs) = indicator_dfs {
            let generated_signals_df = signal_generator::generate_signals(
                processed_data,
                ind_dfs,
                &single_param.signal,
                &processed_template.signal,
            )?;
            signals_df = Some(generated_signals_df);
        }
    }

    // 3. 如果 execution_stage >= "backtest": 执行回测
    if processed_settings.execution_stage >= ExecutionStage::Backtest {
        if let Some(ref sig_df) = signals_df {
            let initial_position_series = risk_adjuster::create_initial_position_series(
                processed_data,
                single_param.backtest.position_pct.value,
            )?;

            let mut first_backtest_df = backtester::run_backtest(
                processed_data,
                sig_df,
                initial_position_series,
                &single_param.backtest,
            )?;

            // 4. 如果 execution_stage >= "backtest" 执行风控+二次回测
            if !processed_settings.skip_risk {
                let adjusted_position_series = risk_adjuster::adjust_position_by_risk(
                    &single_param.backtest,
                    &first_backtest_df,
                    &processed_template.risk,
                    &single_param.risk,
                )?;

                first_backtest_df = backtester::run_backtest(
                    processed_data,
                    sig_df,
                    adjusted_position_series,
                    &single_param.backtest,
                )?;
            }
            backtest_df = Some(first_backtest_df);
        }
    }

    // 5. 如果 execution_stage == "performance": 执行绩效评估
    if processed_settings.execution_stage == ExecutionStage::Performance {
        if let Some(ref bt_df) = backtest_df {
            let analyzed_performance =
                performance_analyzer::analyze_performance(bt_df, &single_param.performance)?;
            performance = Some(analyzed_performance);
        }
    }

    // 6. 最后调用内存优化函数决定返回哪些结果
    let (opt_indicators, opt_signals, opt_backtest, final_perf) = utils::optimize_memory_by_stage(
        processed_settings,
        indicator_dfs,
        signals_df,
        backtest_df,
        performance,
    );

    Ok(BacktestSummary {
        performance: final_perf,
        indicators: opt_indicators,
        signals: opt_signals,
        backtest: opt_backtest,
    })
}

pub fn register_py_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(run_backtest_engine, m)?)?;
    m.add_function(wrap_pyfunction!(signal_generator::py_generate_signals, m)?)?;
    m.add_function(wrap_pyfunction!(indicators::py_calculate_indicators, m)?)?;
    Ok(())
}
