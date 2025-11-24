use pyo3::{create_exception, exceptions::PyException, prelude::*, PyTypeInfo};

use super::error::BacktestError;

create_exception!(pyo3_quant.errors, PyBacktestError, PyException);
create_exception!(
    pyo3_quant.errors,
    PyArrayLengthMismatchError,
    PyBacktestError
);
create_exception!(pyo3_quant.errors, PyMissingColumnError, PyBacktestError);
create_exception!(pyo3_quant.errors, PyNonContiguousDataError, PyBacktestError);
create_exception!(pyo3_quant.errors, PyInvalidParameterError, PyBacktestError);
create_exception!(pyo3_quant.errors, PyEmptyDataFrameError, PyBacktestError);
create_exception!(pyo3_quant.errors, PyContainsNaNError, PyBacktestError);
create_exception!(pyo3_quant.errors, PyATRCalculationError, PyBacktestError);
create_exception!(pyo3_quant.errors, PyOHLCVNotFoundError, PyBacktestError);
create_exception!(pyo3_quant.errors, PyDataValidationError, PyBacktestError);
create_exception!(pyo3_quant.errors, PyMissingDataSourceError, PyBacktestError);
create_exception!(pyo3_quant.errors, PyValidationError, PyBacktestError);

pub fn convert_backtest_error(e: BacktestError) -> PyErr {
    match e {
        BacktestError::ArrayLengthMismatch {
            array_name,
            actual_len,
            expected_len,
        } => PyArrayLengthMismatchError::new_err(format!(
            "数组长度校验失败: {} 长度为 {}, 期望长度为 {}",
            array_name, actual_len, expected_len
        )),
        BacktestError::MissingColumn { column, context } => {
            PyMissingColumnError::new_err(format!("缺失必需列 '{}' (上下文: {})", column, context))
        }
        BacktestError::NonContiguousData { column, context } => {
            PyNonContiguousDataError::new_err(format!(
                "列 '{}' 不是连续内存,请在传入前使用rechunk()处理 (上下文: {})",
                column, context
            ))
        }
        BacktestError::InvalidParameter {
            param_name,
            value,
            reason,
        } => PyInvalidParameterError::new_err(format!(
            "无效参数 '{}' = '{}': {}",
            param_name, value, reason
        )),
        BacktestError::EmptyDataFrame => PyEmptyDataFrameError::new_err("DataFrame为空"),
        BacktestError::ContainsNaN { column, context } => {
            PyContainsNaNError::new_err(format!("列 '{}' 包含NaN值 (上下文: {})", column, context))
        }
        BacktestError::ATRCalculationError { message } => {
            PyATRCalculationError::new_err(format!("ATR计算失败: {}", message))
        }
        BacktestError::OHLCVNotFound => {
            PyOHLCVNotFoundError::new_err("无法从DataContainer提取OHLCV数据")
        }
        BacktestError::DataValidationError { message, context } => {
            PyDataValidationError::new_err(format!("数据验证失败 ({}): {}", context, message))
        }
        BacktestError::MissingDataSource {
            key,
            available_keys,
        } => PyMissingDataSourceError::new_err(format!(
            "数据源中缺少键 '{}',可用键: [{:?}]",
            key, available_keys
        )),
        BacktestError::ValidationError(message) => {
            PyValidationError::new_err(format!("Validation Error: {}", message))
        }
    }
}

pub fn register_py_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add("PyBacktestError", PyBacktestError::type_object(m.py()))?;
    m.add(
        "PyArrayLengthMismatchError",
        PyArrayLengthMismatchError::type_object(m.py()),
    )?;
    m.add(
        "PyMissingColumnError",
        PyMissingColumnError::type_object(m.py()),
    )?;
    m.add(
        "PyNonContiguousDataError",
        PyNonContiguousDataError::type_object(m.py()),
    )?;
    m.add(
        "PyInvalidParameterError",
        PyInvalidParameterError::type_object(m.py()),
    )?;
    m.add(
        "PyEmptyDataFrameError",
        PyEmptyDataFrameError::type_object(m.py()),
    )?;
    m.add(
        "PyContainsNaNError",
        PyContainsNaNError::type_object(m.py()),
    )?;
    m.add(
        "PyATRCalculationError",
        PyATRCalculationError::type_object(m.py()),
    )?;
    m.add(
        "PyOHLCVNotFoundError",
        PyOHLCVNotFoundError::type_object(m.py()),
    )?;
    m.add(
        "PyDataValidationError",
        PyDataValidationError::type_object(m.py()),
    )?;
    m.add(
        "PyMissingDataSourceError",
        PyMissingDataSourceError::type_object(m.py()),
    )?;
    m.add("PyValidationError", PyValidationError::type_object(m.py()))?;
    Ok(())
}
