use crate::types::DataContainer;
use crate::error::{BacktestError, QuantError};
use polars::prelude::DataFrame;

/// 从 DataContainer 中获取基准 OHLCV DataFrame 的工具函数
pub fn get_ohlcv_dataframe(processed_data: &DataContainer) -> Result<&DataFrame, QuantError> {
    processed_data
        .source
        .get(&processed_data.base_data_key)
        .ok_or(BacktestError::OHLCVNotFound.into())
}
