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
        minimal_working_example::polars_data_converter::create_dataframe,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        minimal_working_example::polars_data_converter::process_dataframe,
        m
    )?)?;

    m.add_function(wrap_pyfunction!(
        minimal_working_example::polars_data_converter::test_custom_from_py_object,
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
    // debug
    m.add_function(wrap_pyfunction!(
        minimal_working_example::indicators::debug_bbands::debug_bbands,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        minimal_working_example::indicators::debug_macd::debug_macd,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        minimal_working_example::indicators::debug_adx::debug_adx,
        m
    )?)?;
    Ok(())
}
