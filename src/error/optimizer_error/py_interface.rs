use super::error::OptimizerError;
use pyo3::{exceptions::PyException, prelude::*, PyTypeInfo};

crate::define_exception!(pyo3_quant.errors, PyOptimizerError, PyException);

pub fn convert_optimizer_error(err: OptimizerError) -> PyErr {
    PyOptimizerError::new_err(err.to_string())
}

pub fn register_py_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("PyOptimizerError", PyOptimizerError::type_object(m.py()))?;
    Ok(())
}
