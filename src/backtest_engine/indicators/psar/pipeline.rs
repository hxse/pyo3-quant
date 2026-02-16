use crate::error::{IndicatorError, QuantError};
use polars::prelude::*;

use super::config::PSARConfig;
use super::expr::psar_lazy;

/// 计算层（Eager）。
pub fn psar_eager(ohlcv_df: &DataFrame, config: &PSARConfig) -> Result<DataFrame, QuantError> {
    if ohlcv_df.height() < 2 {
        return Err(
            IndicatorError::DataTooShort("psar".to_string(), 2, ohlcv_df.height() as i64).into(),
        );
    }

    let lazy_df = psar_lazy(ohlcv_df.clone().lazy(), config)?;
    let result_df = lazy_df.collect().map_err(QuantError::from)?;
    Ok(result_df)
}
