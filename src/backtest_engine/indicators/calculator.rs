use crate::backtest_engine::indicators::sma::calculate_sma;
use crate::data_conversion::input::param::Param;
use polars::prelude::*;
use pyo3::{exceptions::PyRuntimeError, PyResult};
use std::collections::HashMap;

/// 计算单个周期的指标
pub fn calculate_single_period_indicators(
    ohlcv_df: &DataFrame,
    period_params: &HashMap<String, HashMap<String, Param>>,
) -> PyResult<DataFrame> {
    // 指定泛型参数避免类型推断失败，初始化为空列 DataFrame
    let mut indicators_df = ohlcv_df
        .select::<Vec<&str>, &str>(vec![])
        .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
    for (indicator_key, param_map) in period_params {
        if indicator_key.starts_with("sma_") {
            if let Some(period_param) = param_map.get("period") {
                let period = period_param.value as i64; // 将 f64 转换为 i64
                let sma_series = calculate_sma(ohlcv_df, period)
                    .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
                // 使用 with_name 返回新 Series，并转换字符串类型
                let named_sma = sma_series.with_name(indicator_key.as_str().into());
                indicators_df
                    .with_column(named_sma)
                    .map_err(|e| PyRuntimeError::new_err(e.to_string()))?;
            }
        }
    }
    Ok(indicators_df)
}
