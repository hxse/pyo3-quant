use crate::data_conversion::{BacktestParams, ProcessedDataDict, RiskTemplate};
use polars::prelude::*;
use pyo3::exceptions::PyKeyError;
use pyo3::prelude::*;
use std::collections::HashMap;

// RiskParams 实际上是 HashMap<String, f64>
use crate::data_conversion::input::param::Param;
type RiskParams = HashMap<String, Param>;

/// 创建初始仓位Series
///
/// # 参数
/// * `processed_data` - 处理后的数据,包含OHLCV DataFrame
/// * `position_pct` - 仓位百分比,用于填充Series的值
///
/// # 返回
/// * `PyResult<Series>` - 长度等于OHLCV行数的Series,值全部为position_pct
///
/// # 错误
/// * 如果processed_data中没有ohlcv字段,返回PyKeyError
pub fn create_initial_position_series(
    processed_data: &ProcessedDataDict,
    position_pct: f64,
) -> PyResult<Series> {
    // 检查是否存在ohlcv
    let ohlcv_vec = &processed_data.ohlcv;
    let ohlcv = ohlcv_vec.first().ok_or_else(|| {
        pyo3::exceptions::PyKeyError::new_err("Empty 'ohlcv' vector in processed_data.ohlcv")
    })?;

    // 获取行数
    let row_count = ohlcv.as_ref().height();

    // 创建Series,值全部为position_pct
    let series = Series::new(
        PlSmallStr::from_static("position"),
        vec![position_pct; row_count],
    );
    Ok(series)
}

pub fn adjust_position_by_risk(
    backtest_params: &BacktestParams,
    result_df: &DataFrame,
    risk_template: &RiskTemplate,
    risk_params: &RiskParams,
) -> PolarsResult<Series> {
    // 返回Series而不是DataFrame

    // // -----------------------------------------------------------------
    // // 🚨 测试目的：尝试访问一个不存在的 "test" 键，并处理缺失情况
    // // -----------------------------------------------------------------
    // let test_value = risk_params.get("test").unwrap().value
    //     .ok_or_else(|| {
    //         // 当键不存在时，返回一个 PyKeyError
    //         PyKeyError::new_err("Required key 'test' not found in risk_params.")
    //     })?; // 问号操作符将 PyKeyError 转换为 PyResult 的 Err 变体并立即返回

    // // 如果代码到达这里，说明 'test' 键存在，我们可以使用 test_value
    // // println!("Found 'test' value: {}", test_value);
    // // -----------------------------------------------------------------

    // 占位实现:返回一个空的Series
    Ok(Series::new(
        PlSmallStr::from_static("adjusted_position"),
        Vec::<f64>::new(),
    ))
}
