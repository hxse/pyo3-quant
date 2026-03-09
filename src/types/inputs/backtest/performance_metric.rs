use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use pyo3_stub_gen::PyStubType;

#[pyclass(eq, eq_int, hash, frozen)]
#[derive(Debug, Clone, Copy, Eq, PartialEq, Hash)]
pub enum PerformanceMetric {
    TotalReturn,
    MaxDrawdown,
    MaxDrawdownDuration,
    SpanMs,
    SpanDays,
    /// 年化夏普比率
    SharpeRatio,
    /// 年化索提诺比率
    SortinoRatio,
    /// 年化卡尔马比率
    CalmarRatio,
    /// 非年化夏普比率（原始）
    SharpeRatioRaw,
    /// 非年化索提诺比率（原始）
    SortinoRatioRaw,
    /// 非年化卡尔马比率（原始）= 总回报率 / 最大回撤
    CalmarRatioRaw,
    TotalTrades,
    AvgDailyTrades,
    AvgTradeIntervalMs,
    AvgTradeIntervalDays,
    WinRate,
    ProfitLossRatio,
    AvgHoldingDuration,
    AvgHoldingDurationMs,
    MaxHoldingDurationMs,
    AvgHoldingDurationDays,
    AvgEmptyDuration,
    AvgEmptyDurationMs,
    MaxHoldingDuration,
    MaxEmptyDuration,
    MaxEmptyDurationMs,
    MaxEmptyDurationDays,
    MaxSafeLeverage,
    AnnualizationFactor,
    HasLeadingNanCount,
}

impl PerformanceMetric {
    /// 返回枚举变体名（用于展示/日志）
    fn variant_name(&self) -> &'static str {
        match self {
            Self::TotalReturn => "TotalReturn",
            Self::MaxDrawdown => "MaxDrawdown",
            Self::MaxDrawdownDuration => "MaxDrawdownDuration",
            Self::SpanMs => "SpanMs",
            Self::SpanDays => "SpanDays",
            Self::SharpeRatio => "SharpeRatio",
            Self::SortinoRatio => "SortinoRatio",
            Self::CalmarRatio => "CalmarRatio",
            Self::SharpeRatioRaw => "SharpeRatioRaw",
            Self::SortinoRatioRaw => "SortinoRatioRaw",
            Self::CalmarRatioRaw => "CalmarRatioRaw",
            Self::TotalTrades => "TotalTrades",
            Self::AvgDailyTrades => "AvgDailyTrades",
            Self::AvgTradeIntervalMs => "AvgTradeIntervalMs",
            Self::AvgTradeIntervalDays => "AvgTradeIntervalDays",
            Self::WinRate => "WinRate",
            Self::ProfitLossRatio => "ProfitLossRatio",
            Self::AvgHoldingDuration => "AvgHoldingDuration",
            Self::AvgHoldingDurationMs => "AvgHoldingDurationMs",
            Self::MaxHoldingDurationMs => "MaxHoldingDurationMs",
            Self::AvgHoldingDurationDays => "AvgHoldingDurationDays",
            Self::AvgEmptyDuration => "AvgEmptyDuration",
            Self::AvgEmptyDurationMs => "AvgEmptyDurationMs",
            Self::MaxHoldingDuration => "MaxHoldingDuration",
            Self::MaxEmptyDuration => "MaxEmptyDuration",
            Self::MaxEmptyDurationMs => "MaxEmptyDurationMs",
            Self::MaxEmptyDurationDays => "MaxEmptyDurationDays",
            Self::MaxSafeLeverage => "MaxSafeLeverage",
            Self::AnnualizationFactor => "AnnualizationFactor",
            Self::HasLeadingNanCount => "HasLeadingNanCount",
        }
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            Self::TotalReturn => "total_return",
            Self::MaxDrawdown => "max_drawdown",
            Self::SpanMs => "span_ms",
            Self::SpanDays => "span_days",
            Self::SharpeRatio => "sharpe_ratio",
            Self::SortinoRatio => "sortino_ratio",
            Self::CalmarRatio => "calmar_ratio",
            Self::SharpeRatioRaw => "sharpe_ratio_raw",
            Self::SortinoRatioRaw => "sortino_ratio_raw",
            Self::CalmarRatioRaw => "calmar_ratio_raw",
            Self::MaxDrawdownDuration => "max_drawdown_duration",
            Self::TotalTrades => "total_trades",
            Self::AvgDailyTrades => "avg_daily_trades",
            Self::AvgTradeIntervalMs => "avg_trade_interval_ms",
            Self::AvgTradeIntervalDays => "avg_trade_interval_days",
            Self::WinRate => "win_rate",
            Self::ProfitLossRatio => "profit_loss_ratio",
            Self::AvgHoldingDuration => "avg_holding_duration",
            Self::AvgHoldingDurationMs => "avg_holding_duration_ms",
            Self::MaxHoldingDurationMs => "max_holding_duration_ms",
            Self::AvgHoldingDurationDays => "avg_holding_duration_days",
            Self::AvgEmptyDuration => "avg_empty_duration",
            Self::AvgEmptyDurationMs => "avg_empty_duration_ms",
            Self::MaxHoldingDuration => "max_holding_duration",
            Self::MaxEmptyDuration => "max_empty_duration",
            Self::MaxEmptyDurationMs => "max_empty_duration_ms",
            Self::MaxEmptyDurationDays => "max_empty_duration_days",
            Self::MaxSafeLeverage => "max_safe_leverage",
            Self::AnnualizationFactor => "annualization_factor",
            Self::HasLeadingNanCount => "has_leading_nan_count",
        }
    }
}

#[gen_stub_pymethods]
#[pymethods]
impl PerformanceMetric {
    fn __str__(&self) -> String {
        self.variant_name().to_string()
    }

    fn __repr__(&self) -> String {
        format!("PerformanceMetric.{}", self.variant_name())
    }
}

impl PyStubType for PerformanceMetric {
    fn type_output() -> pyo3_stub_gen::TypeInfo {
        pyo3_stub_gen::TypeInfo::locally_defined(
            "PerformanceMetric",
            pyo3_stub_gen::ModuleRef::Default,
        )
    }
}

pyo3_stub_gen::inventory::submit! {
    pyo3_stub_gen::type_info::PyEnumInfo {
        enum_id: || std::any::TypeId::of::<PerformanceMetric>(),
        pyclass_name: "PerformanceMetric",
        module: Some("pyo3_quant._pyo3_quant"),
        doc: "性能指标枚举",
        variants: &[
            ("TotalReturn", "总回报率"),
            ("MaxDrawdown", "最大回撤"),
            ("MaxDrawdownDuration", "最大回撤持续时间"),
            ("SpanMs", "时间跨度（毫秒）"),
            ("SpanDays", "时间跨度（天）"),
            ("SharpeRatio", "年化夏普比率"),
            ("SortinoRatio", "年化索提诺比率"),
            ("CalmarRatio", "年化卡尔马比率"),
            ("SharpeRatioRaw", "非年化夏普比率（原始）"),
            ("SortinoRatioRaw", "非年化索提诺比率（原始）"),
            ("CalmarRatioRaw", "非年化卡尔马比率（原始）"),
            ("TotalTrades", "总交易次数"),
            ("AvgDailyTrades", "平均每日交易次数"),
            ("AvgTradeIntervalMs", "平均交易间隔（毫秒）"),
            ("AvgTradeIntervalDays", "平均交易间隔（天）"),
            ("WinRate", "胜率"),
            ("ProfitLossRatio", "盈亏比"),
            ("AvgHoldingDuration", "平均持仓时间"),
            ("AvgHoldingDurationMs", "平均持仓时间（毫秒）"),
            ("MaxHoldingDurationMs", "最大持仓时间（毫秒）"),
            ("AvgHoldingDurationDays", "平均持仓时间（天）"),
            ("AvgEmptyDuration", "平均空仓时间"),
            ("AvgEmptyDurationMs", "平均空仓时间（毫秒）"),
            ("MaxHoldingDuration", "最大持仓时间"),
            ("MaxEmptyDuration", "最大空仓时间"),
            ("MaxEmptyDurationMs", "最大空仓时间（毫秒）"),
            ("MaxEmptyDurationDays", "最大空仓时间（天）"),
            ("MaxSafeLeverage", "最大安全杠杆"),
            ("AnnualizationFactor", "年化因子"),
            ("HasLeadingNanCount", "前置无效数据计数"),
        ],
    }
}
