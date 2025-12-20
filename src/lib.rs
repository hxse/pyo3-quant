mod backtest_engine;
mod data_conversion;
mod error; // 添加这一行

use pyo3::prelude::*;

#[pymodule]
fn pyo3_quant(m: &Bound<'_, PyModule>) -> PyResult<()> {
    let backtest_engine_submodule = PyModule::new(m.py(), "backtest_engine")?;
    backtest_engine::register_py_module(&backtest_engine_submodule)?;
    m.add_submodule(&backtest_engine_submodule)?;

    let errors_submodule = PyModule::new(m.py(), "errors")?;
    error::py_interface::register_py_exceptions(&errors_submodule)?;
    m.add_submodule(&errors_submodule)?;

    Ok(())
}
