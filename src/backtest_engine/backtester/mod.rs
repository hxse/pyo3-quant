use crate::data_conversion::{BacktestParams, DataContainer};
use crate::error::QuantError;
use polars::prelude::*;
use pyo3::prelude::*;
mod atr_calculator;
mod data_preparer;
mod macros;
mod main_loop;
mod output;
mod signal_preprocessor;
pub mod state;

use crate::backtest_engine::utils::get_ohlcv_dataframe;
use {
    atr_calculator::calculate_atr_if_needed, data_preparer::PreparedData, main_loop::run_main_loop,
    output::OutputBuffers, pyo3_polars::PyDataFrame, state::BacktestState,
};

/// 执行回测计算的核心工具函数
///
/// 此函数负责执行单次回测计算，包括数据准备、状态初始化和主循环执行。
/// 不包含回撤检查和二次回测逻辑。
///
/// # 参数
/// * `processed_data` - 处理后的数据容器，包含OHLCV等市场数据
/// * `signals_df` - 信号DataFrame，包含交易信号
/// * `backtest_params` - 回测参数，包含交易策略配置
///
/// # 返回
/// * `Result<OutputBuffers, QuantError>` - 回测输出缓冲区，包含所有回测结果数据
fn run_backtest_calculation(
    processed_data: &DataContainer,
    signals_df: &DataFrame,
    backtest_params: &BacktestParams,
) -> Result<OutputBuffers, QuantError> {
    // 1. 获取 OHLCV DataFrame 并计算 ATR（如果需要）
    let ohlcv = get_ohlcv_dataframe(processed_data)?;
    let atr_series = calculate_atr_if_needed(ohlcv, backtest_params)?;

    // 2. 准备数据，将Polars DataFrame/Series转换为连续的内存数组切片
    let prepared_data = PreparedData::new(processed_data, signals_df, &atr_series)?;

    // 3. 初始化回测状态和输出缓冲区
    let mut backtest_state = BacktestState::new(backtest_params);
    let output_buffers = OutputBuffers::new(backtest_params, prepared_data.time.len());

    // 4. 运行回测主循环
    let output_buffers = run_main_loop(
        &prepared_data,
        &mut backtest_state,
        output_buffers,
        backtest_params,
    )?;

    // 5. 验证所有数组的长度是否相等
    output_buffers.validate_array_lengths()?;

    Ok(output_buffers)
}

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
    // 1. 在准备数据之前，先验证参数的有效性
    backtest_params.validate().map_err(QuantError::Backtest)?;

    // 2. 执行回测计算
    let output_buffers = run_backtest_calculation(processed_data, signals_df, backtest_params)?;

    // 3. 将 OutputBuffers 转换为 DataFrame
    let result_df = output_buffers.to_dataframe()?;

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
