use crate::data_conversion::{BacktestParams, DataContainer};
use crate::error::QuantError;
use polars::prelude::*;
use pyo3::prelude::*;
mod atr_calculator;
mod data_preparer;
mod macros;
mod main_loop;
mod output;
mod pause_control;
mod signal_preprocessor;
pub mod state;

use crate::backtest_engine::utils::get_ohlcv_dataframe;
use {
    atr_calculator::calculate_atr_if_needed, data_preparer::PreparedData, main_loop::run_main_loop,
    output::OutputBuffers, pause_control::apply_pause_control, pyo3_polars::PyDataFrame,
    state::BacktestState,
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

/// 基于已有回测结果执行回测计算的工具函数
///
/// 此函数用于基于已有的回测DataFrame（包含equity和peak_equity）进行回撤检查，
/// 如果触发回撤条件则修改信号并执行第二次回测，否则直接返回原始结果。
///
/// # 参数
/// * `processed_data` - 处理后的数据容器，包含OHLCV等市场数据
/// * `signals_df` - 原始信号DataFrame，包含交易信号
/// * `backtest_params` - 回测参数，包含交易策略和回撤控制配置
/// * `input_backtest_df` - 输入的回测DataFrame，必须包含equity和peak_equity列
///
/// # 返回
/// * `Result<DataFrame, QuantError>` - 最终回测结果DataFrame，包含pause列（如果触发回撤）
fn run_backtest_with_input_df(
    processed_data: &DataContainer,
    signals_df: &DataFrame,
    backtest_params: &BacktestParams,
    input_backtest_df: DataFrame,
) -> Result<DataFrame, QuantError> {
    // 检查是否需要根据回撤情况修改信号并运行第二次回测
    match apply_pause_control(&input_backtest_df, signals_df, backtest_params) {
        Ok(Some((modified_signals_df, pause_series))) => {
            // 执行第二次回测计算
            let output_buffers =
                run_backtest_calculation(processed_data, &modified_signals_df, backtest_params)?;

            // 验证输出缓冲区的数组长度是否相等
            output_buffers.validate_array_lengths()?;

            // 将 OutputBuffers 转换为 DataFrame
            let mut result_df = output_buffers
                .to_dataframe()
                .map_err(QuantError::Backtest)?;

            // 添加pause列到结果DataFrame中
            let lazy_df = result_df
                .lazy()
                .with_column(lit(pause_series).alias("pause"));
            result_df = lazy_df.collect()?;

            Ok(result_df)
        }
        Ok(None) => {
            // 如果不需要修改信号，直接返回输入的DataFrame
            Ok(input_backtest_df)
        }
        Err(e) => {
            // 如果出现错误，直接向上传播
            Err(e)
        }
    }
}

/// 根据回撤情况决定是否执行二次回测的工具函数
///
/// 此函数检查第一次回测的结果，如果回撤超过设定阈值，则修改信号并执行第二次回测。
/// 这是回撤控制机制的核心实现，用于在大幅回撤后暂停交易信号。
///
/// # 参数
/// * `processed_data` - 处理后的数据容器，包含OHLCV等市场数据
/// * `signals_df` - 原始信号DataFrame，包含交易信号
/// * `backtest_params` - 回测参数，包含交易策略和回撤控制配置
/// * `initial_output_buffers` - 第一次回测计算的输出缓冲区
///
/// # 返回
/// * `Result<DataFrame, QuantError>` - 最终回测结果DataFrame，包含pause列（如果触发回撤）
fn run_second_backtest_if_needed(
    processed_data: &DataContainer,
    signals_df: &DataFrame,
    backtest_params: &BacktestParams,
    initial_output_buffers: OutputBuffers,
) -> Result<DataFrame, QuantError> {
    // 检查是否需要根据回撤情况修改信号并运行第二次回测
    let res = {
        // 创建只包含 equity 和 peak_equity 的 DataFrame 用于回撤检查
        let equity_df = initial_output_buffers.to_equity_dataframe()?;
        apply_pause_control(&equity_df, signals_df, backtest_params)
    };
    match res {
        Ok(Some((modified_signals_df, pause_series))) => {
            // 清空旧的 output_buffers 内存以释放资源
            drop(initial_output_buffers);

            // 执行第二次回测计算
            let new_output_buffers =
                run_backtest_calculation(processed_data, &modified_signals_df, backtest_params)?;

            // 验证输出缓冲区的数组长度是否相等
            new_output_buffers.validate_array_lengths()?;

            // 将 OutputBuffers 转换为 DataFrame
            let mut result_df = new_output_buffers
                .to_dataframe()
                .map_err(QuantError::Backtest)?;

            // 添加pause列到结果DataFrame中
            let lazy_df = result_df
                .lazy()
                .with_column(lit(pause_series).alias("pause"));
            result_df = lazy_df.collect()?;

            Ok(result_df)
        }
        Ok(None) => {
            // 如果不需要修改信号，直接使用原始的输出缓冲区转换为DataFrame
            // 验证输出缓冲区的数组长度是否相等
            initial_output_buffers.validate_array_lengths()?;

            // 将 OutputBuffers 转换为 DataFrame
            let result_df = initial_output_buffers
                .to_dataframe()
                .map_err(QuantError::Backtest)?;

            Ok(result_df)
        }
        Err(e) => {
            // 如果出现错误，直接向上传播
            Err(e)
        }
    }
}

/// 执行标准回测计算（无预设输入）
///
/// 这是标准的回测入口函数，用于从零开始执行回测。函数会自动处理回撤检查
/// 和可能的二次回测，确保在大幅回撤时能够正确暂停交易信号。
///
/// # 参数
/// * `processed_data` - 处理后的数据容器，包含OHLCV等市场数据
/// * `signals_df` - 信号DataFrame，包含交易信号
/// * `backtest_params` - 回测参数，包含交易策略和回撤控制配置
///
/// # 返回
/// * `Result<DataFrame, QuantError>` - 完整的回测结果DataFrame，包含所有回测数据和可能的pause列
pub fn run_backtest(
    processed_data: &DataContainer,
    signals_df: &DataFrame,
    backtest_params: &BacktestParams,
) -> Result<DataFrame, QuantError> {
    // 1. 在准备数据之前，先验证参数的有效性
    backtest_params.validate().map_err(QuantError::Backtest)?;

    // 2. 执行第一次回测计算
    let output_buffers = run_backtest_calculation(processed_data, signals_df, backtest_params)?;

    // 3. 检查是否需要执行二次回测（基于回撤情况）
    let result_df =
        run_second_backtest_if_needed(processed_data, signals_df, backtest_params, output_buffers)?;

    Ok(result_df)
}

/// 基于已有回测结果执行回测计算
///
/// 此函数用于基于已有的回测结果进行进一步的回撤检查和处理。如果输入的DataFrame
/// 已经包含pause列，则直接返回；否则进行回撤检查并可能执行第二次回测。
///
/// 典型使用场景：
/// - 在已有回测基础上应用不同的回撤控制参数
/// - 对回测结果进行重新分析和处理
/// - 分步执行复杂的回测策略
///
/// # 参数
/// * `processed_data` - 处理后的数据容器，包含OHLCV等市场数据
/// * `signals_df` - 信号DataFrame，包含交易信号
/// * `backtest_params` - 回测参数，包含交易策略和回撤控制配置
/// * `input_backtest_df` - 输入的回测DataFrame，应包含equity和peak_equity列
///
/// # 返回
/// * `Result<DataFrame, QuantError>` - 最终回测结果DataFrame，包含pause列（如果触发回撤）
pub fn run_backtest_with_input(
    processed_data: &DataContainer,
    signals_df: &DataFrame,
    backtest_params: &BacktestParams,
    input_backtest_df: DataFrame,
) -> Result<DataFrame, QuantError> {
    // 1. 在准备数据之前，先验证参数的有效性
    backtest_params.validate().map_err(QuantError::Backtest)?;

    // 2. 检查是否已经包含pause列，如果有则直接返回（避免重复处理）
    if input_backtest_df
        .get_column_names()
        .iter()
        .any(|name| name.as_str() == "pause")
    {
        return Ok(input_backtest_df);
    }

    // 3. 使用输入的DataFrame进行回撤检查和可能的二次回测
    let result_df = run_backtest_with_input_df(
        processed_data,
        signals_df,
        backtest_params,
        input_backtest_df,
    )?;

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

#[pyfunction(name = "run_backtest_with_input")]
/// Python绑定：基于已有回测结果执行回测计算
///
/// 对应Rust函数：[`run_backtest_with_input`]
///
/// 从Python调用示例：
/// ```python
/// result = run_backtest_with_input(processed_data, signals_df, backtest_params, input_backtest_df)
/// ```
pub fn py_run_backtest_with_input(
    processed_data: DataContainer,
    signals_df_py: PyDataFrame,
    backtest_params: BacktestParams,
    input_backtest_df_py: PyDataFrame,
) -> PyResult<PyDataFrame> {
    // 获取 Rust DataFrame
    let signals_df: DataFrame = signals_df_py.into();
    let input_backtest_df: DataFrame = input_backtest_df_py.into();

    // 调用Rust回测函数并处理错误
    let result_df = run_backtest_with_input(
        &processed_data,
        &signals_df,
        &backtest_params,
        input_backtest_df,
    )
    .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("{}", e)))?;

    // 转换为Python DataFrame并返回
    Ok(PyDataFrame(result_df))
}
