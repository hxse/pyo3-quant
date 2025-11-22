//! 全局列名管理 - 统一管理回测系统中所有使用的列名
//!
//! 这个模块提供了列名的统一管理，避免硬编码字符串和混用问题。

use polars::prelude::PlSmallStr;

/// 列名枚举 - 用于类型安全地表示所有列名
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
pub enum ColumnName {
    // OHLCV数据相关列名
    Time,
    Open,
    High,
    Low,
    Close,
    Volume,

    // 信号相关列名
    EnterLong,
    ExitLong,
    EnterShort,
    ExitShort,

    // OutputBuffers固定列名
    Balance,
    Equity,
    PeakEquity,
    TradePnlPct,
    TotalReturnPct,
    Fee,
    FeeCum,
    CurrentPosition,
    EntryLongPrice,
    EntryShortPrice,
    ExitLongPrice,
    ExitShortPrice,
    RiskInBar,

    // OutputBuffers可选列名
    SlPctPrice,
    TpPctPrice,
    TslPctPrice,
    Atr,
    SlAtrPrice,
    TpAtrPrice,
    TslAtrPrice,
}

impl ColumnName {
    /// 将枚举转换为字符串切片
    pub fn as_str(&self) -> &'static str {
        match self {
            // OHLCV数据相关列名
            ColumnName::Time => "time",
            ColumnName::Open => "open",
            ColumnName::High => "high",
            ColumnName::Low => "low",
            ColumnName::Close => "close",
            ColumnName::Volume => "volume",

            // 信号相关列名
            ColumnName::EnterLong => "enter_long",
            ColumnName::ExitLong => "exit_long",
            ColumnName::EnterShort => "enter_short",
            ColumnName::ExitShort => "exit_short",

            // OutputBuffers固定列名
            ColumnName::Balance => "balance",
            ColumnName::Equity => "equity",
            ColumnName::PeakEquity => "peak_equity",
            ColumnName::TradePnlPct => "trade_pnl_pct",
            ColumnName::TotalReturnPct => "total_return_pct",
            ColumnName::Fee => "fee",
            ColumnName::FeeCum => "fee_cum",
            ColumnName::CurrentPosition => "current_position",
            ColumnName::EntryLongPrice => "entry_long_price",
            ColumnName::EntryShortPrice => "entry_short_price",
            ColumnName::ExitLongPrice => "exit_long_price",
            ColumnName::ExitShortPrice => "exit_short_price",
            ColumnName::RiskInBar => "risk_in_bar",

            // OutputBuffers可选列名
            ColumnName::SlPctPrice => "sl_pct_price",
            ColumnName::TpPctPrice => "tp_pct_price",
            ColumnName::TslPctPrice => "tsl_pct_price",
            ColumnName::Atr => "atr",
            ColumnName::SlAtrPrice => "sl_atr_price",
            ColumnName::TpAtrPrice => "tp_atr_price",
            ColumnName::TslAtrPrice => "tsl_atr_price",
        }
    }

    /// 将枚举转换为PlSmallStr
    pub fn as_pl_small_str(&self) -> PlSmallStr {
        PlSmallStr::from_static(self.as_str())
    }
}
