use pyo3::{exceptions::PyException, prelude::*, PyTypeInfo};

use super::error::SignalError;

crate::define_exception!(pyo3_quant.errors, PySignalError, PyException);
crate::define_exception!(pyo3_quant.errors, PySourceNotFoundError, PySignalError);
crate::define_exception!(
    pyo3_quant.errors,
    PySourceIndexOutOfBoundsError,
    PySignalError
);
crate::define_exception!(pyo3_quant.errors, PyColumnNotFoundError, PySignalError);
crate::define_exception!(pyo3_quant.errors, PyInvalidSourceFormatError, PySignalError);
crate::define_exception!(pyo3_quant.errors, PyMappingColumnNotFound, PySignalError);
crate::define_exception!(pyo3_quant.errors, PyMappingCastError, PySignalError);
crate::define_exception!(pyo3_quant.errors, PyMappingApplyError, PySignalError);
crate::define_exception!(pyo3_quant.errors, PyParameterNotFoundError, PySignalError);
crate::define_exception!(pyo3_quant.errors, PyInvalidInputError, PySignalError);
crate::define_exception!(pyo3_quant.errors, PyParseError, PySignalError);
crate::define_exception!(pyo3_quant.errors, PyInvalidOffsetError, PySignalError);

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
        SignalError::InvalidInput(s) => PyInvalidInputError::new_err(s),
        SignalError::ParseError(s) => PyParseError::new_err(format!("Parse error: {}", s)),
        SignalError::InvalidOffset(s) => {
            PyInvalidOffsetError::new_err(format!("Invalid offset: {}", s))
        }
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
    m.add(
        "PyInvalidInputError",
        PyInvalidInputError::type_object(m.py()),
    )?;
    m.add("PyParseError", PyParseError::type_object(m.py()))?;
    m.add(
        "PyInvalidOffsetError",
        PyInvalidOffsetError::type_object(m.py()),
    )?;
    Ok(())
}
