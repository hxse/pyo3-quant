use crate::data_conversion::{BacktestParams, DataContainer};
use crate::error::QuantError;
use polars::prelude::*;
use pyo3::{prelude::*, types::PyAny};
use pyo3_polars::PyDataFrame;

pub fn run_backtest(
    processed_data: &DataContainer,
    signals_df: &DataFrame,
    backtest_params: &BacktestParams,
) -> Result<DataFrame, QuantError> {
    // 1. 获取数据长度
    let len = processed_data.mapping.height();

    // 占位实现:返回空DataFrame
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
