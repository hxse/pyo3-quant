use crate::types::{BacktestParams, DataContainer};
use crate::error::QuantError;
use polars::prelude::*;
use pyo3::prelude::*;
mod atr_calculator;
mod buffer_slices;
mod data_preparer;
mod main_loop;
mod output;
mod signal_preprocessor;
pub mod state;

use crate::backtest_engine::utils::get_ohlcv_dataframe;
use {
    atr_calculator::calculate_atr_if_needed, data_preparer::PreparedData, main_loop::run_main_loop,
    pyo3_polars::PyDataFrame,
};

/// 执行回测计算
///
/// 这是标准的回测入口函数，用于从零开始执行回测。
///
/// # 参数
/// * `processed_data` - 处理后的数据容器，包含OHLCV等市场数据
/// * `signals_df` - 信号DataFrame，包含交易信号
/// * `backtest_params` - 回测参数，包含交易策略配置
///
/// # 返回
/// * `Result<DataFrame, QuantError>` - 完整的回测结果DataFrame
pub fn run_backtest(
    processed_data: &DataContainer,
    signals_df: &DataFrame,
    backtest_params: &BacktestParams,
) -> Result<DataFrame, QuantError> {
    // 1. 验证参数有效性
    backtest_params.validate().map_err(QuantError::Backtest)?;

    // 2. 获取 OHLCV DataFrame 并计算 ATR（如果需要）
    let ohlcv = get_ohlcv_dataframe(processed_data)?;
    let atr_series = calculate_atr_if_needed(ohlcv, backtest_params)?;

    // 3. 准备数据，将 Polars DataFrame/Series 转换为连续的内存数组切片
    let prepared_data = PreparedData::new(processed_data, signals_df.clone(), &atr_series)?;

    // 4. 运行回测主循环
    let output_buffers = run_main_loop(prepared_data, backtest_params)?;

    // 5. 验证所有数组的长度是否相等
    output_buffers.validate_array_lengths()?;

    // 6. 将 OutputBuffers 转换为 DataFrame
    let mut result_df = output_buffers.to_dataframe()?;

    // 7. 如果信号中存在 has_leading_nan 列，将其复制到结果中
    if let Ok(col) = signals_df.column("has_leading_nan") {
        result_df.with_column(col.clone())?;
    }

    Ok(result_df)
}

#[pyfunction(name = "run_backtest")]
/// Python绑定：执行标准回测计算
///
/// 对应Rust函数：[`run_backtest`]
///
/// 从Python调用示例：
/// ```python
/// result = run_backtest(processed_data, signals_df, backtest_params)
/// ```
pub fn py_run_backtest(
    processed_data: DataContainer,
    signals_df_py: PyDataFrame,
    backtest_params: BacktestParams,
) -> PyResult<PyDataFrame> {
    // 从 PyDataFrame 获取 DataFrame
    let signals_df: DataFrame = signals_df_py.into();

    // 调用Rust回测函数并处理错误
    let result_df = run_backtest(&processed_data, &signals_df, &backtest_params)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("{}", e)))?;

    // 转换为Python DataFrame并返回
    Ok(PyDataFrame(result_df))
}
