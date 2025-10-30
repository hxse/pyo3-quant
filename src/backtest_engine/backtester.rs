use crate::data_conversion::{BacktestParams, DataContainer};
use crate::error::QuantError;
use polars::prelude::*;

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
