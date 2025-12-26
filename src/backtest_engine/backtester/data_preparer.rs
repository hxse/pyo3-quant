use crate::backtest_engine::utils::{column_names::ColumnName, get_ohlcv_dataframe};
use crate::data_conversion::DataContainer;
use crate::error::QuantError;
use polars::prelude::*;
use polars::series::Series;

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
    /// 做多入场信号数组
    pub entry_long: Vec<i32>,
    /// 做多离场信号数组
    pub exit_long: Vec<i32>,
    /// 做空入场信号数组
    pub entry_short: Vec<i32>,
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
        let entry_long = Self::extract_signal_column(signals_df, ColumnName::EntryLong.as_str())?;
        let exit_long = Self::extract_signal_column(signals_df, ColumnName::ExitLong.as_str())?;
        let entry_short = Self::extract_signal_column(signals_df, ColumnName::EntryShort.as_str())?;
        let exit_short = Self::extract_signal_column(signals_df, ColumnName::ExitShort.as_str())?;

        Ok((entry_long, exit_long, entry_short, exit_short))
    }
    /// 准备回测数据，将 Polars DataFrame/Series 转换为连续的内存数组切片
    pub fn new(
        processed_data: &'a DataContainer,
        signals_df: DataFrame,
        atr_series: &'a Option<Series>,
    ) -> Result<PreparedData<'a>, QuantError> {
        // 1. 预处理信号数据（处理冲突和屏蔽）
        let preprocessed_signals_df = super::signal_preprocessor::preprocess_signals(
            signals_df,
            atr_series,
            &processed_data.skip_mask,
        )?;

        // 2. 提取OHLCV数据
        let ohlcv_df = get_ohlcv_dataframe(processed_data)?;
        let time = ohlcv_df
            .column(ColumnName::Time.as_str())?
            .i64()?
            .cont_slice()?;
        let open = ohlcv_df
            .column(ColumnName::Open.as_str())?
            .f64()?
            .cont_slice()?;
        let high = ohlcv_df
            .column(ColumnName::High.as_str())?
            .f64()?
            .cont_slice()?;
        let low = ohlcv_df
            .column(ColumnName::Low.as_str())?
            .f64()?
            .cont_slice()?;
        let close = ohlcv_df
            .column(ColumnName::Close.as_str())?
            .f64()?
            .cont_slice()?;

        // 3. 处理信号列：从预处理后的 DataFrame 提取所有信号
        let (entry_long, exit_long, entry_short, exit_short) =
            Self::extract_all_signals(&preprocessed_signals_df)?;

        // 4. 处理 ATR 数据
        let atr = match atr_series {
            Some(series) => Some(series.f64()?.cont_slice()?.to_vec()),
            None => None,
        };

        // 5. 构建并返回PreparedData结构体
        Ok(PreparedData {
            time,
            open,
            high,
            low,
            close,
            entry_long,
            exit_long,
            entry_short,
            exit_short,
            atr,
        })
    }
}
