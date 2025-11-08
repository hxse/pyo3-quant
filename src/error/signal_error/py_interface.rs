use pyo3::create_exception;
use pyo3::exceptions::PyException;
use pyo3::prelude::*;
use pyo3::PyTypeInfo;

use super::error::SignalError;

create_exception!(pyo3_quant.errors, PySignalError, PyException);
create_exception!(pyo3_quant.errors, PySourceNotFoundError, PySignalError);
create_exception!(
    pyo3_quant.errors,
    PySourceIndexOutOfBoundsError,
    PySignalError
);
create_exception!(pyo3_quant.errors, PyColumnNotFoundError, PySignalError);
create_exception!(pyo3_quant.errors, PyInvalidSourceFormatError, PySignalError);
create_exception!(pyo3_quant.errors, PyMappingColumnNotFound, PySignalError);
create_exception!(pyo3_quant.errors, PyMappingCastError, PySignalError);
create_exception!(pyo3_quant.errors, PyMappingApplyError, PySignalError);
create_exception!(pyo3_quant.errors, PyParameterNotFoundError, PySignalError);

pub fn convert_signal_error(e: SignalError) -> PyErr {
    match e {
        SignalError::SourceNotFound(s) => PySourceNotFoundError::new_err(s),
        SignalError::SourceIndexOutOfBounds(s) => PySourceIndexOutOfBoundsError::new_err(s),
        SignalError::ColumnNotFound(s) => PyColumnNotFoundError::new_err(s),
        SignalError::InvalidSourceFormat(s) => PyInvalidSourceFormatError::new_err(s),
        SignalError::MappingColumnNotFound(s) => PyMappingColumnNotFound::new_err(s),
        SignalError::MappingCastError(s) => PyMappingCastError::new_err(s),
        SignalError::MappingApplyError(s) => PyMappingApplyError::new_err(s),
        SignalError::ParameterNotFound(s) => PyParameterNotFoundError::new_err(s),
    }
}

pub fn register_py_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("PySignalError", PySignalError::type_object(m.py()))?;
    m.add(
        "PySourceNotFoundError",
        PySourceNotFoundError::type_object(m.py()),
    )?;
    m.add(
        "PySourceIndexOutOfBoundsError",
        PySourceIndexOutOfBoundsError::type_object(m.py()),
    )?;
    m.add(
        "PyColumnNotFoundError",
        PyColumnNotFoundError::type_object(m.py()),
    )?;
    m.add(
        "PyInvalidSourceFormatError",
        PyInvalidSourceFormatError::type_object(m.py()),
    )?;
    m.add(
        "PyMappingColumnNotFound",
        PyMappingColumnNotFound::type_object(m.py()),
    )?;
    m.add(
        "PyMappingCastError",
        PyMappingCastError::type_object(m.py()),
    )?;
    m.add(
        "PyMappingApplyError",
        PyMappingApplyError::type_object(m.py()),
    )?;
    m.add(
        "PyParameterNotFoundError",
        PyParameterNotFoundError::type_object(m.py()),
    )?;
    Ok(())
}
