use pyo3::prelude::*;
use pyo3_stub_gen::PyStubType;

#[pyclass(eq, eq_int, hash, frozen)]
#[derive(Debug, Clone, Copy, Eq, PartialEq, Hash)]
pub enum PerformanceMetric {
    TotalReturn,
    MaxDrawdown,
    MaxDrawdownDuration,
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
    WinRate,
    ProfitLossRatio,
    AvgHoldingDuration,
    AvgEmptyDuration,
    MaxHoldingDuration,
    MaxEmptyDuration,
    MaxSafeLeverage,
    AnnualizationFactor,
    HasLeadingNanCount,
}

impl PerformanceMetric {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::TotalReturn => "total_return",
            Self::MaxDrawdown => "max_drawdown",
            Self::SharpeRatio => "sharpe_ratio",
            Self::SortinoRatio => "sortino_ratio",
            Self::CalmarRatio => "calmar_ratio",
            Self::SharpeRatioRaw => "sharpe_ratio_raw",
            Self::SortinoRatioRaw => "sortino_ratio_raw",
            Self::CalmarRatioRaw => "calmar_ratio_raw",
            Self::MaxDrawdownDuration => "max_drawdown_duration",
            Self::TotalTrades => "total_trades",
            Self::AvgDailyTrades => "avg_daily_trades",
            Self::WinRate => "win_rate",
            Self::ProfitLossRatio => "profit_loss_ratio",
            Self::AvgHoldingDuration => "avg_holding_duration",
            Self::AvgEmptyDuration => "avg_empty_duration",
            Self::MaxHoldingDuration => "max_holding_duration",
            Self::MaxEmptyDuration => "max_empty_duration",
            Self::MaxSafeLeverage => "max_safe_leverage",
            Self::AnnualizationFactor => "annualization_factor",
            Self::HasLeadingNanCount => "has_leading_nan_count",
        }
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
            ("SharpeRatio", "年化夏普比率"),
            ("SortinoRatio", "年化索提诺比率"),
            ("CalmarRatio", "年化卡尔马比率"),
            ("SharpeRatioRaw", "非年化夏普比率（原始）"),
            ("SortinoRatioRaw", "非年化索提诺比率（原始）"),
            ("CalmarRatioRaw", "非年化卡尔马比率（原始）"),
            ("TotalTrades", "总交易次数"),
            ("AvgDailyTrades", "平均每日交易次数"),
            ("WinRate", "胜率"),
            ("ProfitLossRatio", "盈亏比"),
            ("AvgHoldingDuration", "平均持仓时间"),
            ("AvgEmptyDuration", "平均空仓时间"),
            ("MaxHoldingDuration", "最大持仓时间"),
            ("MaxEmptyDuration", "最大空仓时间"),
            ("MaxSafeLeverage", "最大安全杠杆"),
            ("AnnualizationFactor", "年化因子"),
            ("HasLeadingNanCount", "前置无效数据计数"),
        ],
    }
}
