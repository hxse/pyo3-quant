use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::PyDataFrame;

/// 原有函数，保持不变。
#[pyfunction]
pub fn sum_as_string(a: usize, b: usize) -> PyResult<String> {
    Ok((a + b + 6).to_string())
}

#[pyfunction]
pub fn create_dataframe() -> PyResult<PyDataFrame> {
    let df = df![
        PlSmallStr::from_static("column_a") => &[1i64, 2, 5],
        PlSmallStr::from_static("column_b") => &[4i64, 5, 7],
    ]
    .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;
    Ok(PyDataFrame(df))
}

#[pyfunction]
pub fn process_dataframe(pydf: PyDataFrame) -> PyResult<PyDataFrame> {
    let mut df: DataFrame = pydf.into(); // 转换为 Rust DataFrame

    // 示例处理：添加新列
    df.with_column(Series::new(
        PlSmallStr::from_static("year"),
        vec![2023_i64, 2027],
    ))
    .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    Ok(PyDataFrame(df)) // 直接返回修改后的 df，无需 clone()
}
