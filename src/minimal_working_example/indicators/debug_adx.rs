use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::PyDataFrame;

use crate::backtest_engine::indicators::adx::{adx_eager, ADXConfig};

/// ADX 指标调试函数，用于对比 Rust 和 talib 实现的 PLUS_DM 指标差异。
///
/// 接受 PyDataFrame, period 作为参数。
/// 将 PyDataFrame 转换为 DataFrame。
/// 调用 `crate::backtest_engine::indicators::adx::adx_eager`。
/// 从返回的 Series 中提取 Plus DM。
/// 将提取的 Series (plus_dm) 组装成 DataFrame。
/// 转换为 PyDataFrame 返回。
///
/// # 参数
/// - `pydf`: 输入的 PyDataFrame，包含 "high", "low", "close" 列。
/// - `period`: PLUS_DM 的周期长度。
///
/// # 返回
/// 包含 "plus_dm" 列的 PyDataFrame。
#[pyfunction]
pub fn debug_adx(pydf: PyDataFrame, period: i64) -> PyResult<PyDataFrame> {
    let df: DataFrame = pydf.into(); // 将 PyDataFrame 转换为 Rust DataFrame

    let config = ADXConfig::new(period);

    // 调用 adx_eager 计算函数，它会返回 (adx, adxr, plus_dm, minus_dm)
    let (_, _, plus_dm_series, _) = adx_eager(&df, &config)
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    // 将返回的 Series 组装成新的 DataFrame
    let result_df = DataFrame::new(vec![plus_dm_series
        .with_name(PlSmallStr::from("plus_dm"))
        .into_column()])
    .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    Ok(PyDataFrame(result_df)) // 转换为 PyDataFrame 返回
}
