mod backtest_engine;
mod data_conversion;
mod minimal_working_example;

use pyo3::prelude::*;

#[pymodule]
fn pyo3_quant(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(
        minimal_working_example::simple::sum_as_string,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        minimal_working_example::simple::create_dataframe,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        minimal_working_example::simple::process_dataframe,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        minimal_working_example::rayon_with_polars::process_dataframes_vec,
        m
    )?)?; // 通过模块暴露
    m.add_function(wrap_pyfunction!(
        minimal_working_example::calculate_metrics::calculate_metrics,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(backtest_engine::run_backtest_engine, m)?)?;
    Ok(())
}
