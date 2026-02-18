use super::{
    action_resolver, backtester, data_ops, indicators, optimizer, performance_analyzer,
    sensitivity, signal_generator, walk_forward,
};
use pyo3::prelude::*;

/// 将子模块注册到 Python 的 `sys.modules`
///
/// 这样 `import pyo3_quant.backtest_engine.xxx` 会直接命中 Rust 已注册的模块对象，
/// 避免 Python 侧再做动态注入。
fn register_submodule_in_sys_modules(
    py: Python<'_>,
    full_module_name: &str,
    submodule: &Bound<'_, PyModule>,
) -> PyResult<()> {
    py.import("sys")?
        .getattr("modules")?
        .set_item(full_module_name, submodule)?;
    Ok(())
}

/// 统一注册所有 backtest_engine 子模块。
pub(super) fn register_all_submodules(m: &Bound<'_, PyModule>) -> PyResult<()> {
    let py = m.py();

    let indicators_submodule = PyModule::new(py, "indicators")?;
    indicators_submodule.add_function(wrap_pyfunction!(
        indicators::py_calculate_indicators,
        &indicators_submodule
    )?)?;
    m.add_submodule(&indicators_submodule)?;
    register_submodule_in_sys_modules(
        py,
        "pyo3_quant.backtest_engine.indicators",
        &indicators_submodule,
    )?;

    let signal_generator_submodule = PyModule::new(py, "signal_generator")?;
    signal_generator_submodule.add_function(wrap_pyfunction!(
        signal_generator::py_generate_signals,
        &signal_generator_submodule
    )?)?;
    m.add_submodule(&signal_generator_submodule)?;
    register_submodule_in_sys_modules(
        py,
        "pyo3_quant.backtest_engine.signal_generator",
        &signal_generator_submodule,
    )?;

    let backtester_submodule = PyModule::new(py, "backtester")?;
    backtester_submodule.add_function(wrap_pyfunction!(
        backtester::py_run_backtest,
        &backtester_submodule
    )?)?;
    backtester_submodule.add_function(wrap_pyfunction!(
        backtester::py_frame_state_name,
        &backtester_submodule
    )?)?;
    m.add_submodule(&backtester_submodule)?;
    register_submodule_in_sys_modules(
        py,
        "pyo3_quant.backtest_engine.backtester",
        &backtester_submodule,
    )?;

    let performance_analyzer_submodule = PyModule::new(py, "performance_analyzer")?;
    performance_analyzer_submodule.add_function(wrap_pyfunction!(
        performance_analyzer::py_analyze_performance,
        &performance_analyzer_submodule
    )?)?;
    m.add_submodule(&performance_analyzer_submodule)?;
    register_submodule_in_sys_modules(
        py,
        "pyo3_quant.backtest_engine.performance_analyzer",
        &performance_analyzer_submodule,
    )?;

    let optimizer_submodule = PyModule::new(py, "optimizer")?;
    optimizer_submodule.add_function(wrap_pyfunction!(
        optimizer::py_run_optimizer,
        &optimizer_submodule
    )?)?;
    optimizer_submodule.add_function(wrap_pyfunction!(
        optimizer::py_run_optimizer_benchmark,
        &optimizer_submodule
    )?)?;
    m.add_submodule(&optimizer_submodule)?;
    register_submodule_in_sys_modules(
        py,
        "pyo3_quant.backtest_engine.optimizer",
        &optimizer_submodule,
    )?;

    let wf_submodule = PyModule::new(py, "walk_forward")?;
    walk_forward::register_py_module(&wf_submodule)?;
    m.add_submodule(&wf_submodule)?;
    register_submodule_in_sys_modules(
        py,
        "pyo3_quant.backtest_engine.walk_forward",
        &wf_submodule,
    )?;

    let action_resolver_submodule = PyModule::new(py, "action_resolver")?;
    action_resolver::register_py_module(&action_resolver_submodule)?;
    m.add_submodule(&action_resolver_submodule)?;
    register_submodule_in_sys_modules(
        py,
        "pyo3_quant.backtest_engine.action_resolver",
        &action_resolver_submodule,
    )?;

    let sensitivity_submodule = PyModule::new(py, "sensitivity")?;
    sensitivity_submodule.add_function(wrap_pyfunction!(
        sensitivity::py_run_sensitivity_test,
        &sensitivity_submodule
    )?)?;
    m.add_submodule(&sensitivity_submodule)?;
    register_submodule_in_sys_modules(
        py,
        "pyo3_quant.backtest_engine.sensitivity",
        &sensitivity_submodule,
    )?;

    let data_ops_submodule = PyModule::new(py, "data_ops")?;
    data_ops::register_py_module(&data_ops_submodule)?;
    m.add_submodule(&data_ops_submodule)?;
    register_submodule_in_sys_modules(
        py,
        "pyo3_quant.backtest_engine.data_ops",
        &data_ops_submodule,
    )?;

    Ok(())
}
