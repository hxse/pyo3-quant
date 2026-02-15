use pyo3::{
    exceptions::{PyException, PyValueError},
    prelude::*,
    PyTypeInfo,
};

use super::backtest_error::py_interface::{
    convert_backtest_error, register_py_module as register_backtest_errors,
};
use super::indicator_error::py_interface::{
    convert_indicator_error, register_py_module as register_indicator_errors,
};
use super::optimizer_error::py_interface::{
    convert_optimizer_error, register_py_module as register_optimizer_errors,
};
use super::quant_error::QuantError;
use super::signal_error::py_interface::{
    convert_signal_error, register_py_module as register_signal_errors,
};

crate::define_exception!(pyo3_quant.errors, PyQuantError, PyException);

impl From<QuantError> for PyErr {
    fn from(err: QuantError) -> PyErr {
        match err {
            QuantError::Signal(e) => convert_signal_error(e),
            QuantError::Indicator(e) => convert_indicator_error(e),
            QuantError::Backtest(e) => convert_backtest_error(e),
            QuantError::Optimizer(e) => convert_optimizer_error(e),
            QuantError::PyO3(e) => e,
            QuantError::Polars(e) => PyQuantError::new_err(e.to_string()),
            QuantError::InfrastructureError(s) => PyQuantError::new_err(s),
            QuantError::InvalidParam(s) => PyValueError::new_err(s),
        }
    }
}

pub fn register_py_exceptions(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("PyQuantError", PyQuantError::type_object(m.py()))?;
    register_backtest_errors(m)?;
    register_indicator_errors(m)?;
    register_signal_errors(m)?;
    register_optimizer_errors(m)?;
    Ok(())
}
