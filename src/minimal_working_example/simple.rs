use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::PyDataFrame;

/// 原有函数，保持不变。
#[pyfunction]
pub fn sum_as_string(a: usize, b: usize) -> PyResult<String> {
    Ok((a + b + 5).to_string())
}
