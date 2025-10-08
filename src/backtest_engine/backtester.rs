use crate::data_conversion::{BacktestParams, ProcessedDataDict};
use polars::prelude::*;

pub fn run_backtest(
    processed_data: &ProcessedDataDict,
    signals_df: &DataFrame,
    position_series: Series,
    backtest_params: &BacktestParams,
) -> PolarsResult<DataFrame> {
    // 占位实现:返回空DataFrame
    Ok(DataFrame::empty())
}
