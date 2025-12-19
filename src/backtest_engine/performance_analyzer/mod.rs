use crate::data_conversion::types::{
    backtest_summary::PerformanceMetrics,
    param_set::{PerformanceMetric, PerformanceParams},
};
use crate::error::QuantError;
use polars::prelude::*;
use pyo3::{prelude::*, types::PyAny};
use pyo3_polars::PyDataFrame;
use std::collections::HashMap;

pub fn analyze_performance(
    _backtest_df: &DataFrame,
    performance_params: &PerformanceParams,
) -> Result<PerformanceMetrics, QuantError> {
    let mut result = HashMap::new();

    for metric in performance_params.metrics.iter() {
        let value = match metric {
            PerformanceMetric::TotalReturn => 0.0,
            PerformanceMetric::SharpeRatio => 0.0,
            PerformanceMetric::MaxDrawdown => 0.0,
        };

        result.insert(metric.as_str().to_string(), value);
    }

    Ok(result)
}

#[pyfunction(name = "analyze_performance")]
pub fn py_analyze_performance(
    backtest_df_py: PyDataFrame,
    performance_params_py: &Bound<'_, PyAny>,
) -> PyResult<PerformanceMetrics> {
    // 1. 将 Python 对象转换为 Rust 类型
    let backtest_df: DataFrame = backtest_df_py.into();
    let performance_params: PerformanceParams = performance_params_py.extract()?;

    // 2. 调用原始的 analyze_performance 函数
    let result = analyze_performance(&backtest_df, &performance_params)?;

    // 3. PyO3 会自动将 PerformanceMetrics (HashMap<String, f64>) 转换为 Python 字典
    Ok(result)
}
