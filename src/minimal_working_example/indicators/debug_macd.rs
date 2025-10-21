use polars::prelude::*;
use pyo3::prelude::*;
use pyo3_polars::PyDataFrame;

/// MACD 指标调试函数,用于对比 Rust 和 talib 实现的 MACD 指标差异。
///
/// 接受 PyDataFrame, fast_period, slow_period, signal_period 作为参数。
/// 将 PyDataFrame 转换为 DataFrame。
/// 调用 `crate::backtest_engine::indicators::macd::macd_eager`。
/// 将返回的3个 Series (macd, signal, histogram) 组装成 DataFrame。
/// 转换为 PyDataFrame 返回。
///
/// # 参数
/// - `pydf`: 输入的 PyDataFrame,包含 "close" 列。
/// - `fast_period`: 快速 EMA 周期。
/// - `slow_period`: 慢速 EMA 周期。
/// - `signal_period`: 信号线 EMA 周期。
///
/// # 返回
/// 包含 "MACD_12_26_9", "MACDs_12_26_9", "MACDh_12_26_9" 列的 PyDataFrame。
#[pyfunction]
pub fn debug_macd(
    pydf: PyDataFrame,
    fast_period: i64,
    slow_period: i64,
    signal_period: i64,
) -> PyResult<PyDataFrame> {
    let df: DataFrame = pydf.into(); // 将 PyDataFrame 转换为 Rust DataFrame

    // 构建列名
    let macd_name = format!("MACD_{}_{}_{}", fast_period, slow_period, signal_period);
    let signal_name = format!("MACDs_{}_{}_{}", fast_period, slow_period, signal_period);
    let histogram_name = format!("MACDh_{}_{}_{}", fast_period, slow_period, signal_period);

    let lazy_df = df.lazy();
    let result_lazy_df = crate::backtest_engine::indicators::macd::macd_lazy(
        lazy_df,
        "close", // 输入列名
        fast_period,
        slow_period,
        signal_period,
        macd_name.as_str(),
        signal_name.as_str(),
        histogram_name.as_str(),
    )
    .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    let result_df = result_lazy_df
        .collect()
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    let macd = result_df
        .column(macd_name.as_str())
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?
        .clone();
    let signal = result_df
        .column(signal_name.as_str())
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?
        .clone();
    let histogram = result_df
        .column(histogram_name.as_str())
        .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?
        .clone();

    // 将返回的 Series 组装成新的 DataFrame
    let final_df = DataFrame::new(vec![
        macd.with_name(PlSmallStr::from(macd_name.as_str()))
            .into_column(),
        signal
            .with_name(PlSmallStr::from(signal_name.as_str()))
            .into_column(),
        histogram
            .with_name(PlSmallStr::from(histogram_name.as_str()))
            .into_column(),
    ])
    .map_err(|e| pyo3::exceptions::PyValueError::new_err(e.to_string()))?;

    Ok(PyDataFrame(final_df)) // 转换为 PyDataFrame 返回
}
