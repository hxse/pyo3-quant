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

    // 信号相关列名
    EntryLong,
    ExitLong,
    EntryShort,
    ExitShort,

    // OutputBuffers固定列名
    Balance,
    Equity,
    CurrentDrawdown,
    TradePnlPct,
    TotalReturnPct,
    Fee,
    FeeCum,
    EntryLongPrice,
    EntryShortPrice,
    ExitLongPrice,
    ExitShortPrice,

    // OutputBuffers可选列名
    SlPctPriceLong,
    SlPctPriceShort,
    TpPctPriceLong,
    TpPctPriceShort,
    TslPctPriceLong,
    TslPctPriceShort,
    Atr,
    SlAtrPriceLong,
    SlAtrPriceShort,
    TpAtrPriceLong,
    TpAtrPriceShort,
    TslAtrPriceLong,
    TslAtrPriceShort,

    // PSAR 跟踪止损价格
    TslPsarPriceLong,
    TslPsarPriceShort,

    // Risk State Output
    RiskInBarDirection,
    FirstEntrySide,

    // 帧事件位掩码
    FrameState,

    // 追踪指标状态
    HasLeadingNan,
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

            // 信号相关列名
            ColumnName::EntryLong => "entry_long",
            ColumnName::ExitLong => "exit_long",
            ColumnName::EntryShort => "entry_short",
            ColumnName::ExitShort => "exit_short",

            // OutputBuffers固定列名
            ColumnName::Balance => "balance",
            ColumnName::Equity => "equity",
            ColumnName::CurrentDrawdown => "current_drawdown",
            ColumnName::TradePnlPct => "trade_pnl_pct",
            ColumnName::TotalReturnPct => "total_return_pct",
            ColumnName::Fee => "fee",
            ColumnName::FeeCum => "fee_cum",
            ColumnName::EntryLongPrice => "entry_long_price",
            ColumnName::EntryShortPrice => "entry_short_price",
            ColumnName::ExitLongPrice => "exit_long_price",
            ColumnName::ExitShortPrice => "exit_short_price",

            // OutputBuffers可选列名
            ColumnName::SlPctPriceLong => "sl_pct_price_long",
            ColumnName::SlPctPriceShort => "sl_pct_price_short",
            ColumnName::TpPctPriceLong => "tp_pct_price_long",
            ColumnName::TpPctPriceShort => "tp_pct_price_short",
            ColumnName::TslPctPriceLong => "tsl_pct_price_long",
            ColumnName::TslPctPriceShort => "tsl_pct_price_short",
            ColumnName::Atr => "atr",
            ColumnName::SlAtrPriceLong => "sl_atr_price_long",
            ColumnName::SlAtrPriceShort => "sl_atr_price_short",
            ColumnName::TpAtrPriceLong => "tp_atr_price_long",
            ColumnName::TpAtrPriceShort => "tp_atr_price_short",
            ColumnName::TslAtrPriceLong => "tsl_atr_price_long",
            ColumnName::TslAtrPriceShort => "tsl_atr_price_short",

            // PSAR 跟踪止损价格
            ColumnName::TslPsarPriceLong => "tsl_psar_price_long",
            ColumnName::TslPsarPriceShort => "tsl_psar_price_short",

            // Risk State Output
            ColumnName::RiskInBarDirection => "risk_in_bar_direction",
            ColumnName::FirstEntrySide => "first_entry_side",

            // 帧事件位掩码
            ColumnName::FrameState => "frame_state",

            // 追踪指标状态
            ColumnName::HasLeadingNan => "has_leading_nan",
        }
    }

    /// 将枚举转换为PlSmallStr
    pub fn as_pl_small_str(&self) -> PlSmallStr {
        PlSmallStr::from_static(self.as_str())
    }
}
