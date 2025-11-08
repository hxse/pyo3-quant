use crate::data_conversion::{BacktestParams, DataContainer};
use crate::error::QuantError;
use polars::prelude::*;
use pyo3::{prelude::*, types::PyAny};
mod atr_calculator;
mod data_preparer;
mod main_loop;
mod output;
mod state;

use atr_calculator::calculate_atr_if_needed;
use data_preparer::{apply_skip_mask, get_ohlcv_dataframe, prepare_data};
use main_loop::run_main_loop;
use output::OutputBuffers;
use pyo3_polars::PyDataFrame;
use state::BacktestState;

pub fn run_backtest(
    processed_data: &DataContainer,
    signals_df: &DataFrame,
    backtest_params: &BacktestParams,
) -> Result<DataFrame, QuantError> {
    // 在准备数据之前，先应用 skip_mask 逻辑
    let signals_df_after_mask = apply_skip_mask(&processed_data.skip_mask, signals_df)?;

    // 1. 准备数据，将Polars DataFrame/Series转换为连续的内存数组切片
    let prepared_data = prepare_data(processed_data, &signals_df_after_mask)?;

    // 2. 获取 OHLCV DataFrame 并计算 ATR（如果需要）
    let ohlcv = get_ohlcv_dataframe(processed_data)?;
    let atr_series = calculate_atr_if_needed(ohlcv, backtest_params)?;

    // 3. 初始化回测状态和输出缓冲区
    let mut backtest_state = BacktestState::new(backtest_params);
    let output_buffers = OutputBuffers::new(backtest_params, prepared_data.time.len());

    // 4. 运行回测主循环
    let _output_buffers = run_main_loop(
        &prepared_data,
        &mut backtest_state,
        output_buffers,
        &atr_series,
        backtest_params,
    )?;

    // 临时返回空DataFrame，实际回测逻辑待实现
    Ok(DataFrame::new(vec![])?)
}

#[pyfunction(name = "run_backtest")]
pub fn py_run_backtest(
    py: Python,
    processed_data_py: &Bound<'_, PyAny>,
    signals_df_py: &Bound<'_, PyAny>,
    backtest_params_py: &Bound<'_, PyAny>,
) -> PyResult<PyDataFrame> {
    let processed_data: DataContainer = processed_data_py.extract()?;
    let signals_df: DataFrame = signals_df_py.extract::<PyDataFrame>()?.into();
    let backtest_params: BacktestParams = backtest_params_py.extract()?;

    let result_df = run_backtest(&processed_data, &signals_df, &backtest_params)
        .map_err(|e| PyErr::new::<pyo3::exceptions::PyValueError, _>(format!("{}", e)))?;

    Ok(PyDataFrame(result_df))
}
