use pyo3::prelude::*;

pub mod params;
pub mod rayon_with_polars;
pub mod simple;

pub mod calculate_metrics;
pub mod polars_data_converter;

pub fn register_py_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(simple::sum_as_string, m)?)?;
    m.add_function(wrap_pyfunction!(
        polars_data_converter::create_dataframe,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        polars_data_converter::process_dataframe,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        polars_data_converter::test_custom_from_py_object,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(
        rayon_with_polars::process_dataframes_vec,
        m
    )?)?;
    m.add_function(wrap_pyfunction!(calculate_metrics::calculate_metrics, m)?)?;
    Ok(())
}
