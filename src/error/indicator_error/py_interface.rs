use pyo3::{create_exception, exceptions::PyException, prelude::*, PyTypeInfo};

use super::error::IndicatorError;

create_exception!(pyo3_quant.errors, PyIndicatorError, PyException);
create_exception!(
    pyo3_quant.errors,
    PyIndicatorParameterNotFoundError,
    PyIndicatorError
);
create_exception!(
    pyo3_quant.errors,
    PyIndicatorInvalidParameterError,
    PyIndicatorError
);
create_exception!(
    pyo3_quant.errors,
    PyIndicatorColumnNotFoundError,
    PyIndicatorError
);
create_exception!(
    pyo3_quant.errors,
    PyIndicatorDataTooShortError,
    PyIndicatorError
);
create_exception!(
    pyo3_quant.errors,
    PyIndicatorNotImplementedError,
    PyIndicatorError
);
create_exception!(
    pyo3_quant.errors,
    PyDataSourceNotFoundError,
    PyIndicatorError
);
create_exception!(
    pyo3_quant.errors,
    PyDataSourceLengthMismatchError,
    PyIndicatorError
);

pub fn convert_indicator_error(e: IndicatorError) -> PyErr {
    match e {
        IndicatorError::ParameterNotFound(param, indicator) => {
            PyIndicatorParameterNotFoundError::new_err(format!(
                "Parameter '{}' not found for indicator '{}'",
                param, indicator
            ))
        }
        IndicatorError::InvalidParameter(param, value) => {
            PyIndicatorInvalidParameterError::new_err(format!(
                "Invalid parameter for '{0}': {1}",
                param, value
            ))
        }
        IndicatorError::ColumnNotFound(col) => {
            PyIndicatorColumnNotFoundError::new_err(format!("Input column '{0}' not found", col))
        }
        IndicatorError::DataTooShort(indicator, period, series_len) => {
            PyIndicatorDataTooShortError::new_err(format!(
                "Input data is too short to calculate indicator '{0}' with period '{1}' data count '{2}'",
                indicator, period, series_len
            ))
        }

        IndicatorError::NotImplemented(indicator) => {
            PyIndicatorNotImplementedError::new_err(format!(
                "Indicator '{0}' is not implemented or supported.",
                indicator
            ))
        }
        IndicatorError::DataSourceNotFound(source) => {
            PyDataSourceNotFoundError::new_err(format!("Data source '{}' not found", source))
        }
        IndicatorError::DataSourceLengthMismatch(source, data_len, param_len) => {
            PyDataSourceLengthMismatchError::new_err(format!(
                "Data source '{}' length ({}) does not match indicator parameters length ({})",
                source, data_len, param_len
            ))
        }
    }
}

pub fn register_py_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("PyIndicatorError", PyIndicatorError::type_object(m.py()))?;
    m.add(
        "PyIndicatorParameterNotFoundError",
        PyIndicatorParameterNotFoundError::type_object(m.py()),
    )?;
    m.add(
        "PyIndicatorInvalidParameterError",
        PyIndicatorInvalidParameterError::type_object(m.py()),
    )?;
    m.add(
        "PyIndicatorColumnNotFoundError",
        PyIndicatorColumnNotFoundError::type_object(m.py()),
    )?;
    m.add(
        "PyIndicatorDataTooShortError",
        PyIndicatorDataTooShortError::type_object(m.py()),
    )?;
    m.add(
        "PyIndicatorNotImplementedError",
        PyIndicatorNotImplementedError::type_object(m.py()),
    )?;
    m.add(
        "PyDataSourceNotFoundError",
        PyDataSourceNotFoundError::type_object(m.py()),
    )?;
    m.add(
        "PyDataSourceLengthMismatchError",
        PyDataSourceLengthMismatchError::type_object(m.py()),
    )?;
    Ok(())
}
