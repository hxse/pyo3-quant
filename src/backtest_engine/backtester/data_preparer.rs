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

impl<'a> PreparedData<'a> {
    /// 从 DataFrame 中提取信号列并转换为 Vec<i32>
    ///
    /// # 参数
    /// * `df` - 包含信号列的 DataFrame
    /// * `column_name` - 要提取的列名
    ///
    /// # 返回
    /// * `Result<Vec<i32>, QuantError>` - 转换后的 i32 向量或错误信息
    fn extract_signal_column(df: &DataFrame, column_name: &str) -> Result<Vec<i32>, QuantError> {
        let result = df
            .column(column_name)?
            .cast(&DataType::Int32)?
            .i32()?
            .rechunk()
            .cont_slice()?
            .to_vec();
        Ok(result)
    }

    /// 从 DataFrame 中提取所有信号列
    ///
    /// # 参数
    /// * `signals_df` - 包含所有信号列的 DataFrame
    ///
    /// # 返回
    /// * `Result<(Vec<i32>, Vec<i32>, Vec<i32>, Vec<i32>), QuantError>` - 包含四个信号列的元组
    fn extract_all_signals(
        signals_df: &DataFrame,
    ) -> Result<(Vec<i32>, Vec<i32>, Vec<i32>, Vec<i32>), QuantError> {
        let enter_long = Self::extract_signal_column(signals_df, "enter_long")?;
        let exit_long = Self::extract_signal_column(signals_df, "exit_long")?;
        let enter_short = Self::extract_signal_column(signals_df, "enter_short")?;
        let exit_short = Self::extract_signal_column(signals_df, "exit_short")?;

        Ok((enter_long, exit_long, enter_short, exit_short))
    }
    /// 准备回测数据，将 Polars DataFrame/Series 转换为连续的内存数组切片
    pub fn new(
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

        // 2. 处理信号列：使用辅助函数提取所有信号
        let (enter_long, exit_long, enter_short, exit_short) =
            Self::extract_all_signals(signals_df)?;

        // 3. 处理 ATR 数据
        let atr = match atr_series {
            Some(series) => Some(series.f64()?.cont_slice()?.to_vec()),
            None => None,
        };

        // 6. 构建并返回PreparedData结构体
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

    /// 更新信号数组
    ///
    /// # 参数
    /// * `signals_df` - 新的信号 DataFrame
    ///
    /// # 返回
    /// * `Result<(), QuantError>` - 更新成功或错误信息
    ///
    /// # 注意
    /// 此方法只更新信号相关字段，其他字段保持只读
    pub fn update_signals(&mut self, signals_df: &DataFrame) -> Result<(), QuantError> {
        // 使用辅助函数提取所有信号
        let (enter_long, exit_long, enter_short, exit_short) =
            Self::extract_all_signals(signals_df)?;

        // 检查长度是否匹配
        let expected_len = self.enter_long.len();
        if enter_long.len() != expected_len
            || exit_long.len() != expected_len
            || enter_short.len() != expected_len
            || exit_short.len() != expected_len
        {
            return Err(BacktestError::ArrayLengthMismatch {
                array_name: "signals".to_string(),
                actual_len: enter_long.len(),
                expected_len,
            }
            .into());
        }

        // 更新信号字段
        self.enter_long = enter_long;
        self.exit_long = exit_long;
        self.enter_short = enter_short;
        self.exit_short = exit_short;

        Ok(())
    }
}
