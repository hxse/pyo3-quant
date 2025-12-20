use polars::lazy::dsl::{col, lit, when};
use polars::prelude::*;

// 從 ema.rs 導入封裝的 EMA 邏輯
use super::{registry::Indicator, utils::null_to_nan_expr};
use crate::backtest_engine::indicators::ema::{ema_expr, EMAConfig};
use crate::data_conversion::types::param::Param;
use crate::error::{IndicatorError, QuantError};
use std::collections::HashMap;

/// MACD 的配置結構體
/// MACD 的配置結構體
pub struct MACDConfig {
    pub fast_period: i64,      // 快速周期
    pub slow_period: i64,      // 慢速周期
    pub signal_period: i64,    // 信號周期
    pub column_name: String,   // 輸入列名
    pub fast_ema_name: String, // 快速 EMA 臨時列名
    pub slow_ema_name: String, // 慢速 EMA 臨時列名
    pub macd_alias: String,    // MACD 輸出別名
    pub signal_alias: String,  // Signal 輸出別名
    pub hist_alias: String,    // Histogram 輸出別名
}

impl MACDConfig {
    pub fn new(fast_period: i64, slow_period: i64, signal_period: i64) -> Self {
        Self {
            fast_period,
            slow_period,
            signal_period,
            column_name: "close".to_string(),
            fast_ema_name: "fast_ema".to_string(),
            slow_ema_name: "slow_ema".to_string(),
            macd_alias: "macd".to_string(),
            signal_alias: "signal".to_string(),
            hist_alias: "hist".to_string(),
        }
    }
}

// 表達式層（使用封裝的 ema_expr）
pub fn macd_expr(
    config: &MACDConfig,
) -> Result<(Expr, Expr, Expr, Expr, Expr, Expr, Expr, Expr), QuantError> {
    let column_name = &config.column_name;
    let mut fast_period = config.fast_period;
    let mut slow_period = config.slow_period;
    let signal_period = config.signal_period;
    let macd_alias = &config.macd_alias;
    let signal_alias = &config.signal_alias;
    let hist_alias = &config.hist_alias;
    let fast_ema_name = &config.fast_ema_name;
    let slow_ema_name = &config.slow_ema_name;

    // 如果 slow < fast，交換
    if slow_period < fast_period {
        std::mem::swap(&mut fast_period, &mut slow_period);
    }

    // 計算 start_offset_fast（還原舊邏輯，以確保對齊和正確初始化）
    let start_offset_fast = slow_period - fast_period;

    // 1. 計算快速 EMA (fast_period)，使用封裝的 EMAConfig
    let mut fast_config = EMAConfig::new(fast_period);
    fast_config.column_name = column_name.clone();
    fast_config.alias_name = fast_ema_name.clone();
    fast_config.processed_column_alias = format!("{}_processed_temp", fast_config.alias_name);
    fast_config.initial_value_temp = format!("{}_initial_value_temp", fast_config.alias_name);
    fast_config.start_offset = start_offset_fast;
    fast_config.ignore_nulls = false; // 匹配舊 MACD 邏輯，避免忽略 NULL 導致偏差
    let (processed_close_fast, fast_ema) = ema_expr(&fast_config)?;

    // 2. 計算慢速 EMA (slow_period)
    let mut slow_config = EMAConfig::new(slow_period);
    slow_config.column_name = column_name.clone();
    slow_config.alias_name = slow_ema_name.clone();
    slow_config.processed_column_alias = format!("{}_processed_temp", slow_config.alias_name);
    slow_config.initial_value_temp = format!("{}_initial_value_temp", slow_config.alias_name);
    slow_config.start_offset = 0;
    slow_config.ignore_nulls = false;
    let (processed_close_slow, slow_ema) = ema_expr(&slow_config)?;

    // 3. MACD Line = fast_ema - slow_ema
    let macd = (fast_ema.clone() - slow_ema.clone())
        .cast(DataType::Float64)
        .alias(macd_alias);

    // 4. Signal Line = EMA(MACD Line, signal_period)
    let start_offset_signal = slow_period - 1; // 匹配 TA-Lib 的 fastEMABuffer[0]
    let mut signal_config = EMAConfig::new(signal_period);
    signal_config.column_name = macd_alias.clone(); // 使用 MACD Line 作为输入
    signal_config.alias_name = signal_alias.clone();
    signal_config.processed_column_alias = format!("{}_processed_temp", signal_config.alias_name);
    signal_config.initial_value_temp = format!("{}_initial_value_temp", signal_config.alias_name);
    signal_config.start_offset = start_offset_signal;
    signal_config.ignore_nulls = false;
    let (processed_macd, signal) = ema_expr(&signal_config)?;

    // 5. Histogram = MACD Line - Signal Line
    let hist = (col(macd_alias) - col(signal_alias))
        .cast(DataType::Float64)
        .alias(hist_alias);

    Ok((
        processed_close_fast,
        processed_close_slow,
        fast_ema,
        slow_ema,
        macd,
        processed_macd,
        signal,
        hist,
    ))
}

/// MACD 的藍圖層實現
pub fn macd_lazy(lazy_df: LazyFrame, config: &MACDConfig) -> Result<LazyFrame, QuantError> {
    let macd_alias = &config.macd_alias;
    let signal_alias = &config.signal_alias;
    let hist_alias = &config.hist_alias;
    let fast_period = config.fast_period;
    let slow_period = config.slow_period;
    let signal_period = config.signal_period;

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

    // 計算 lookback (使用交換後的 slow_period)
    let mut temp_slow = slow_period;
    let mut temp_fast = fast_period;
    if temp_slow < temp_fast {
        std::mem::swap(&mut temp_slow, &mut temp_fast);
    }
    let slow_ema_lookback = temp_slow - 1;
    let signal_lookback = signal_period - 1;
    let total_lookback = slow_ema_lookback + signal_lookback;

    let lazy_df = lazy_df
        .with_row_index("index", None)
        .with_column(processed_close_fast)
        .with_column(fast_ema)
        .with_column(processed_close_slow)
        .with_column(slow_ema)
        .with_column(macd)
        // 確保 MACD Line 在索引 slow_ema_lookback 之前為 NULL
        .with_column(
            when(
                col("index")
                    .cast(DataType::Int64)
                    .lt(lit(slow_ema_lookback)),
            )
            .then(lit(NULL))
            .otherwise(col(macd_alias))
            .cast(DataType::Float64)
            .alias(macd_alias),
        )
        // 為 signal EMA 創建臨時列，確保索引 slow_ema_lookback 到 total_lookback 的值有效
        .with_column(
            when(
                col("index")
                    .cast(DataType::Int64)
                    .lt(lit(slow_ema_lookback)),
            )
            .then(lit(NULL))
            .otherwise(col(macd_alias))
            .cast(DataType::Float64)
            .alias(&config.macd_alias), // Use config.macd_alias for the temp column
        )
        .with_column(processed_macd)
        .with_column(signal)
        .with_column(hist)
        // 統一對齊 MACD、Signal 和 Histogram
        .with_column(
            when(col("index").cast(DataType::Int64).lt(lit(total_lookback)))
                .then(lit(NULL))
                .otherwise(col(macd_alias))
                .cast(DataType::Float64)
                .alias(macd_alias),
        )
        .with_column(
            when(col("index").cast(DataType::Int64).lt(lit(total_lookback)))
                .then(lit(NULL))
                .otherwise(col(signal_alias))
                .cast(DataType::Float64)
                .alias(signal_alias),
        )
        .with_column(
            when(col("index").cast(DataType::Int64).lt(lit(total_lookback)))
                .then(lit(NULL))
                .otherwise(col(hist_alias))
                .cast(DataType::Float64)
                .alias(hist_alias),
        )
        // 在蓝图层将所有 MACD 输出的 NULL 转换为 NaN
        .with_column(null_to_nan_expr(macd_alias))
        .with_column(null_to_nan_expr(signal_alias))
        .with_column(null_to_nan_expr(hist_alias))
        .select(&[col(macd_alias), col(signal_alias), col(hist_alias)]);

    Ok(lazy_df)
}

/// MACD 的急切計算包裝函數
pub fn macd_eager(
    ohlcv_df: &DataFrame,
    config: &MACDConfig,
) -> Result<(Series, Series, Series), QuantError> {
    // 1. 邊界檢查
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

    // 2. 調用 macd_lazy 並 collect
    let df = macd_lazy(ohlcv_df.clone().lazy(), config)?
        .collect()
        .map_err(QuantError::from)?;

    // 3. 返回三個 Series
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

pub struct MacdIndicator;

impl Indicator for MacdIndicator {
    fn calculate(
        &self,
        ohlcv_df: &DataFrame,
        indicator_key: &str,
        param_map: &HashMap<String, Param>,
    ) -> Result<Vec<Series>, QuantError> {
        let fast_period = param_map
            .get("fast_period")
            .and_then(|p| Some(p.value as i64))
            .ok_or_else(|| {
                IndicatorError::InvalidParameter(
                    indicator_key.to_string(),
                    "Missing or invalid 'fast_period' parameter".to_string(),
                )
            })?;

        let slow_period = param_map
            .get("slow_period")
            .and_then(|p| Some(p.value as i64))
            .ok_or_else(|| {
                IndicatorError::InvalidParameter(
                    indicator_key.to_string(),
                    "Missing or invalid 'slow_period' parameter".to_string(),
                )
            })?;

        let signal_period = param_map
            .get("signal_period")
            .and_then(|p| Some(p.value as i64))
            .ok_or_else(|| {
                IndicatorError::InvalidParameter(
                    indicator_key.to_string(),
                    "Missing or invalid 'signal_period' parameter".to_string(),
                )
            })?;

        let mut config = MACDConfig::new(fast_period, slow_period, signal_period);
        config.macd_alias = format!("{}_macd", indicator_key);
        config.signal_alias = format!("{}_signal", indicator_key);
        config.hist_alias = format!("{}_hist", indicator_key);

        let (macd_series, signal_series, hist_series) = macd_eager(ohlcv_df, &config)?;
        Ok(vec![macd_series, hist_series, signal_series])
    }
}
