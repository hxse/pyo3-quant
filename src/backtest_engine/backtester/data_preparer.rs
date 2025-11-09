use crate::backtest_engine::indicators::atr::{atr_eager, ATRConfig};
use crate::data_conversion::{input::param_set::BacktestParams, DataContainer};
use crate::error::backtest_error::BacktestError;
use crate::error::QuantError;
use polars::prelude::*;
use polars::series::Series;

/// 从 DataContainer 中获取 OHLCV DataFrame 的工具函数
pub fn get_ohlcv_dataframe(processed_data: &DataContainer) -> Result<&DataFrame, QuantError> {
    processed_data
        .source
        .get("ohlcv")
        .and_then(|vec| vec.first())
        .ok_or(BacktestError::OHLCVNotFound)
        .map_err(Into::into)
}

/// 根据skip_mask处理信号，返回一个新的DataFrame。
/// # 逻辑:
/// 1. 入场信号 (`enter_long`, `enter_short`): 如果 `skip_mask` 为 `true`，则强制设为 `false`。
/// 2. 出场信号 (`exit_long`, `exit_short`): 如果 `skip_mask` 为 `true`，则强制设为 `true`。
/// 3. skip_mask为false的时候, 复用原始的`enter_long`, `enter_short`, `exit_long`, `exit_short`信号
pub fn apply_skip_mask(
    skip_mask: &Series,
    signals_df: &DataFrame,
) -> Result<DataFrame, QuantError> {
    let new_df = signals_df
        .clone() // 必须：lazy() 消耗所有权
        .lazy()
        .with_column(lit(skip_mask.clone()).alias("skip_mask"))
        .with_column(
            when(col("skip_mask"))
                .then(lit(false))
                .otherwise(col("enter_long"))
                .alias("enter_long"),
        )
        .with_column(
            when(col("skip_mask"))
                .then(lit(false))
                .otherwise(col("enter_short"))
                .alias("enter_short"),
        )
        .with_column(
            when(col("skip_mask"))
                .then(lit(true))
                .otherwise(col("exit_long"))
                .alias("exit_long"),
        )
        .with_column(
            when(col("skip_mask"))
                .then(lit(true))
                .otherwise(col("exit_short"))
                .alias("exit_short"),
        )
        .select([
            col("enter_long"),
            col("exit_long"),
            col("enter_short"),
            col("exit_short"),
        ])
        .collect()?;
    Ok(new_df)
}
/// 预处理数据结构体，包含所有回测所需的连续内存数组切片
pub struct PreparedData<'a> {
    /// 时间戳数组
    pub time: &'a [i64],
    /// 开盘价数组
    pub open: &'a [f64],
    /// 最高价数组
    pub high: &'a [f64],
    /// 最低价数组
    pub low: &'a [f64],
    /// 收盘价数组
    pub close: &'a [f64],
    /// 成交量数组
    pub volume: &'a [f64],
    /// 做多入场信号数组
    pub enter_long: Vec<i32>,
    /// 做多离场信号数组
    pub exit_long: Vec<i32>,
    /// 做空入场信号数组
    pub enter_short: Vec<i32>,
    /// 做空离场信号数组
    pub exit_short: Vec<i32>,
    /// ATR 指标数组，可选
    pub atr: Option<Vec<f64>>,
}

/// 准备回测数据，将 Polars DataFrame/Series 转换为连续的内存数组切片
pub fn prepare_data<'a>(
    processed_data: &'a DataContainer,
    signals_df: &'a DataFrame,
    atr_series: &'a Option<Series>,
) -> Result<PreparedData<'a>, QuantError> {
    // 1. 提取OHLCV数据
    let ohlcv_df = get_ohlcv_dataframe(processed_data)?;
    let time = ohlcv_df.column("time")?.i64()?.cont_slice()?;
    let open = ohlcv_df.column("open")?.f64()?.cont_slice()?;
    let high = ohlcv_df.column("high")?.f64()?.cont_slice()?;
    let low = ohlcv_df.column("low")?.f64()?.cont_slice()?;
    let close = ohlcv_df.column("close")?.f64()?.cont_slice()?;
    let volume = ohlcv_df.column("volume")?.f64()?.cont_slice()?;

    // 2. 处理信号列：内联转换逻辑
    let enter_long: Vec<i32> = {
        let series = signals_df.column("enter_long")?;
        let casted = series.cast(&DataType::Int32)?;
        casted.i32()?.cont_slice()?.to_vec()
    };
    let exit_long: Vec<i32> = {
        let series = signals_df.column("exit_long")?;
        let casted = series.cast(&DataType::Int32)?;
        casted.i32()?.cont_slice()?.to_vec()
    };
    let enter_short: Vec<i32> = {
        let series = signals_df.column("enter_short")?;
        let casted = series.cast(&DataType::Int32)?;
        casted.i32()?.cont_slice()?.to_vec()
    };
    let exit_short: Vec<i32> = {
        let series = signals_df.column("exit_short")?;
        let casted = series.cast(&DataType::Int32)?;
        casted.i32()?.cont_slice()?.to_vec()
    };

    // 3. 处理 ATR 数据
    let atr = match atr_series {
        Some(series) => {
            let atr_vec = series.f64()?.cont_slice()?.to_vec();
            Some(atr_vec)
        }
        None => None,
    };

    // 4. 构建并返回PreparedData结构体
    Ok(PreparedData {
        time,
        open,
        high,
        low,
        close,
        volume,
        enter_long,
        exit_long,
        enter_short,
        exit_short,
        atr,
    })
}
