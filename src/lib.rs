mod backtest_engine;
mod data_conversion;
mod minimal_working_example;

use pyo3::prelude::*;

#[pymodule]
fn pyo3_quant(m: &Bound<'_, PyModule>) -> PyResult<()> {
    let backtest_engine_submodule = PyModule::new(m.py(), "backtest_engine")?;
    backtest_engine::register_py_module(&backtest_engine_submodule)?;
    m.add_submodule(&backtest_engine_submodule)?;

    let data_conversion_submodule = PyModule::new(m.py(), "data_conversion")?;
    data_conversion::register_py_module(&data_conversion_submodule)?;
    m.add_submodule(&data_conversion_submodule)?;

    let minimal_working_example_submodule = PyModule::new(m.py(), "minimal_working_example")?;
    minimal_working_example::register_py_module(&minimal_working_example_submodule)?;
    m.add_submodule(&minimal_working_example_submodule)?;

    Ok(())
}
