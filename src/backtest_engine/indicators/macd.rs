use polars::lazy::dsl::{col, lit, when};
use polars::prelude::*;

// 從 ema.rs 導入封裝的 EMA 邏輯
use crate::backtest_engine::indicators::ema::{ema_expr, EMAConfig};
use crate::error::{IndicatorError, QuantError};

/// MACD 的配置結構體
pub struct MACDConfig {
    pub column_name: String,  // 輸入列名
    pub fast_period: i64,     // 快速周期
    pub slow_period: i64,     // 慢速周期
    pub signal_period: i64,   // 信號周期
    pub macd_alias: String,   // MACD 輸出別名
    pub signal_alias: String, // Signal 輸出別名
    pub hist_alias: String,   // Histogram 輸出別名
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

    // 如果 slow < fast，交換
    if slow_period < fast_period {
        std::mem::swap(&mut fast_period, &mut slow_period);
    }

    // 計算 start_offset_fast（還原舊邏輯，以確保對齊和正確初始化）
    let start_offset_fast = slow_period - fast_period;

    // 1. 計算快速 EMA (fast_period)，使用封裝的 EMAConfig
    let mut fast_config = EMAConfig::new(fast_period);
    fast_config.column_name = column_name.clone();
    fast_config.alias_name = format!("{}_fast_ema_temp_{}", column_name, fast_period);
    fast_config.processed_column_alias = format!("{}_processed_temp", fast_config.alias_name);
    fast_config.initial_value_temp = format!("{}_initial_value_temp", fast_config.alias_name);
    fast_config.start_offset = start_offset_fast;
    fast_config.ignore_nulls = false; // 匹配舊 MACD 邏輯，避免忽略 NULL 導致偏差
    let (processed_close_fast, fast_ema) = ema_expr(&fast_config)?;

    // 2. 計算慢速 EMA (slow_period)
    let mut slow_config = EMAConfig::new(slow_period);
    slow_config.column_name = column_name.clone();
    slow_config.alias_name = format!("{}_slow_ema_temp_{}", column_name, slow_period);
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
    signal_config.column_name = "macd_temp".to_string();
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
pub fn macd_lazy(
    lazy_df: LazyFrame,
    column_name: &str,
    fast_period: i64,
    slow_period: i64,
    signal_period: i64,
    macd_alias: &str,
    signal_alias: &str,
    hist_alias: &str,
) -> Result<LazyFrame, QuantError> {
    let config = MACDConfig {
        column_name: column_name.to_string(),
        fast_period,
        slow_period,
        signal_period,
        macd_alias: macd_alias.to_string(),
        signal_alias: signal_alias.to_string(),
        hist_alias: hist_alias.to_string(),
    };
    let (
        processed_close_fast,
        processed_close_slow,
        fast_ema,
        slow_ema,
        macd,
        processed_macd,
        signal,
        hist,
    ) = macd_expr(&config)?;

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
            .alias("macd_temp"),
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
        .select(&[col(macd_alias), col(signal_alias), col(hist_alias)]);

    Ok(lazy_df)
}

/// MACD 的急切計算包裝函數
pub fn macd_eager(
    ohlcv_df: &DataFrame,
    column_name: &str,
    fast_period: i64,
    slow_period: i64,
    signal_period: i64,
    macd_alias: &str,
    signal_alias: &str,
    hist_alias: &str,
) -> Result<(Series, Series, Series), QuantError> {
    // 1. 邊界檢查
    if fast_period <= 0 {
        return Err(IndicatorError::InvalidParameter(
            "macd".to_string(),
            "Fast period must be positive".to_string(),
        )
        .into());
    }
    if slow_period <= 0 {
        return Err(IndicatorError::InvalidParameter(
            "macd".to_string(),
            "Slow period must be positive".to_string(),
        )
        .into());
    }
    if signal_period <= 0 {
        return Err(IndicatorError::InvalidParameter(
            "macd".to_string(),
            "Signal period must be positive".to_string(),
        )
        .into());
    }

    let series_len = ohlcv_df.height();
    let min_len = (std::cmp::max(fast_period, slow_period) + signal_period - 2);
    if series_len < min_len as usize {
        return Err(IndicatorError::DataTooShort("macd".to_string(), min_len).into());
    }

    // 2. 調用 macd_lazy 並 collect
    let df = macd_lazy(
        ohlcv_df.clone().lazy(),
        column_name,
        fast_period,
        slow_period,
        signal_period,
        macd_alias,
        signal_alias,
        hist_alias,
    )?
    .collect()
    .map_err(QuantError::from)?;

    // 3. 返回三個 Series
    let macd = df
        .column(macd_alias)
        .map_err(QuantError::from)?
        .as_materialized_series()
        .clone();
    let signal = df
        .column(signal_alias)
        .map_err(QuantError::from)?
        .as_materialized_series()
        .clone();
    let hist = df
        .column(hist_alias)
        .map_err(QuantError::from)?
        .as_materialized_series()
        .clone();

    Ok((macd, signal, hist))
}
