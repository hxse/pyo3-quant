use super::submodule_init::register_all_submodules;
use super::top_level_api::{py_run_backtest_engine, py_run_single_backtest};
use pyo3::prelude::*;

/// 注册 PyO3 模块的所有函数。
///
/// 统一暴露主回测入口与各子模块函数。
pub fn register_py_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(py_run_backtest_engine, m)?)?;
    m.add_function(wrap_pyfunction!(py_run_single_backtest, m)?)?;
    register_all_submodules(m)?;
    Ok(())
}
