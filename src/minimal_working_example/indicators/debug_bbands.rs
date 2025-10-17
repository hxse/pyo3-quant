use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::PyDataFrame;

/// 通用指标调试函数，用于对比 Rust 和 pandas-ta 实现的 bbands 指标差异。
///
/// 接受 PyDataFrame, length, std 作为参数。
/// 将 PyDataFrame 转换为 DataFrame。
/// 调用 `crate::backtest_engine::indicators::bbands::calculate_bbands`。
/// 将返回的5个 Series (lower, middle, upper, bandwidth, percent) 组装成 DataFrame。
/// 转换为 PyDataFrame 返回。
///
/// # 参数
/// - `pydf`: 输入的 PyDataFrame，包含 "close" 列。
/// - `length`: 布林带的周期长度。
/// - `std`: 标准差乘数。
///
/// # 返回
/// 包含 "lower", "middle", "upper", "bandwidth", "percent" 列的 PyDataFrame。
#[pyfunction]
pub fn debug_bbands(pydf: PyDataFrame, length: i64, std: f64) -> PyResult<PyDataFrame> {
    let df: DataFrame = pydf.into(); // 将 PyDataFrame 转换为 Rust DataFrame

    // 调用 bbands 计算函数
    let (lower, middle, upper, bandwidth, percent) =
        crate::backtest_engine::indicators::bbands::bbands_eager(&df, length, std)
            .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    // 将返回的 Series 组装成新的 DataFrame
    let result_df = DataFrame::new(vec![
        lower.with_name(PlSmallStr::from("lower")).into_column(),
        middle.with_name(PlSmallStr::from("middle")).into_column(),
        upper.with_name(PlSmallStr::from("upper")).into_column(),
        bandwidth
            .with_name(PlSmallStr::from("bandwidth"))
            .into_column(),
        percent.with_name(PlSmallStr::from("percent")).into_column(),
    ])
    .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    Ok(PyDataFrame(result_df)) // 转换为 PyDataFrame 返回
}
