use super::config::MACDConfig;
use super::expr::{final_null_to_nan_exprs, macd_expr, warmup_mask_exprs};
use crate::error::{IndicatorError, QuantError};
use polars::lazy::dsl::col;
use polars::prelude::*;

pub fn macd_lazy(lazy_df: LazyFrame, config: &MACDConfig) -> Result<LazyFrame, QuantError> {
    let (
        processed_close_fast,
        processed_close_slow,
        fast_ema,
        slow_ema,
        macd,
        processed_macd,
        signal,
        hist,
    ) = macd_expr(config)?;

    let (mask_macd_before_slow, mask_macd, mask_signal, total_lookback, _) =
        warmup_mask_exprs(config);

    let mask_hist = when(col("index").cast(DataType::Int64).lt(lit(total_lookback)))
        .then(lit(NULL))
        .otherwise(col(&config.hist_alias))
        .cast(DataType::Float64)
        .alias(&config.hist_alias);

    let (macd_nan, signal_nan, hist_nan) = final_null_to_nan_exprs(config);

    let lazy_df = lazy_df
        .with_row_index("index", None)
        .with_column(processed_close_fast)
        .with_column(fast_ema)
        .with_column(processed_close_slow)
        .with_column(slow_ema)
        .with_column(macd)
        .with_column(mask_macd_before_slow)
        // 保持原实现的重复写入语义，避免行为漂移。
        .with_column(
            when(
                col("index")
                    .cast(DataType::Int64)
                    .lt(lit(config.slow_period.max(config.fast_period) - 1)),
            )
            .then(lit(NULL))
            .otherwise(col(&config.macd_alias))
            .cast(DataType::Float64)
            .alias(&config.macd_alias),
        )
        .with_column(processed_macd)
        .with_column(signal)
        .with_column(hist)
        .with_column(mask_macd)
        .with_column(mask_signal)
        .with_column(mask_hist)
        .with_column(macd_nan)
        .with_column(signal_nan)
        .with_column(hist_nan);

    Ok(lazy_df)
}

pub fn macd_eager(
    ohlcv_df: &DataFrame,
    config: &MACDConfig,
) -> Result<(Series, Series, Series), QuantError> {
    if config.fast_period <= 0 {
        return Err(IndicatorError::InvalidParameter(
            "macd".to_string(),
            "Fast period must be positive".to_string(),
        )
        .into());
    }
    if config.slow_period <= 0 {
        return Err(IndicatorError::InvalidParameter(
            "macd".to_string(),
            "Slow period must be positive".to_string(),
        )
        .into());
    }
    if config.signal_period <= 0 {
        return Err(IndicatorError::InvalidParameter(
            "macd".to_string(),
            "Signal period must be positive".to_string(),
        )
        .into());
    }

    let series_len = ohlcv_df.height();
    let min_len = std::cmp::max(config.fast_period, config.slow_period) + config.signal_period - 2;
    if series_len < min_len as usize {
        return Err(
            IndicatorError::DataTooShort("macd".to_string(), min_len, series_len as i64).into(),
        );
    }

    let df = macd_lazy(ohlcv_df.clone().lazy(), config)?
        .select([
            col(&config.macd_alias),
            col(&config.signal_alias),
            col(&config.hist_alias),
        ])
        .collect()
        .map_err(QuantError::from)?;

    let macd = df
        .column(&config.macd_alias)
        .map_err(QuantError::from)?
        .as_materialized_series()
        .clone();
    let signal = df
        .column(&config.signal_alias)
        .map_err(QuantError::from)?
        .as_materialized_series()
        .clone();
    let hist = df
        .column(&config.hist_alias)
        .map_err(QuantError::from)?
        .as_materialized_series()
        .clone();

    Ok((macd, signal, hist))
}
