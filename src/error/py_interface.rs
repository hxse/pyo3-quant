use pyo3::prelude::*;
use pyo3::{
    create_exception, exceptions::PyException, types::PyModule, Bound, PyErr, PyResult, PyTypeInfo,
};

use super::backtest_error::BacktestError;
use super::indicator_error::IndicatorError;
use super::quant_error::QuantError;
use super::signal_error::SignalError;

// 定义自定义 Python 异常的基类
create_exception!(pyo3_quant.errors, PyQuantError, PyException);
create_exception!(pyo3_quant.errors, PySignalError, PyQuantError);
create_exception!(pyo3_quant.errors, PyIndicatorError, PyQuantError);
create_exception!(pyo3_quant.errors, PyBacktestError, PyQuantError);

// 定义 SignalError 相关的 Python 异常
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

// 定义 IndicatorError 相关的 Python 异常
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

// 辅助函数：将 SignalError 转换为 PyErr
fn convert_signal_error(signal_error: SignalError) -> PyErr {
    match signal_error {
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

// 辅助函数：将 IndicatorError 转换为 PyErr
fn convert_indicator_error(indicator_error: IndicatorError) -> PyErr {
    match indicator_error {
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
        IndicatorError::DataTooShort(indicator, period) => {
            PyIndicatorDataTooShortError::new_err(format!(
                "Input data is too short to calculate indicator '{0}' with period '{1}'",
                indicator, period
            ))
        }
        IndicatorError::NotImplemented(indicator) => {
            PyIndicatorNotImplementedError::new_err(format!(
                "Indicator '{0}' is not implemented or supported.",
                indicator
            ))
        }
    }
}

// 辅助函数：将 BacktestError 转换为 PyErr
fn convert_backtest_error(backtest_error: BacktestError) -> PyErr {
    PyBacktestError::new_err(backtest_error.to_string())
}

// 实现从 QuantError 到 PyErr 的转换，以便在 PyO3 接口层抛出
impl From<QuantError> for PyErr {
    fn from(err: QuantError) -> PyErr {
        match err {
            QuantError::Signal(signal_error) => convert_signal_error(signal_error),
            QuantError::Indicator(indicator_error) => convert_indicator_error(indicator_error),
            QuantError::Backtest(backtest_error) => convert_backtest_error(backtest_error),
            QuantError::PyO3(e) => e,
            QuantError::Polars(e) => PyQuantError::new_err(e.to_string()),
            QuantError::InfrastructureError(s) => PyQuantError::new_err(s),
        }
    }
}

pub fn register_py_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("PyQuantError", PyQuantError::type_object(m.py()))?;
    m.add("PySignalError", PySignalError::type_object(m.py()))?;
    m.add("PyIndicatorError", PyIndicatorError::type_object(m.py()))?;
    m.add("PyBacktestError", PyBacktestError::type_object(m.py()))?;

    // 注册 SignalError 相关的异常
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

    // 注册 IndicatorError 相关的异常
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

    Ok(())
}
