use pyo3::prelude::*;

/// 优化目标指标枚举
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum OptimizeMetric {
    /// 年化夏普比率
    SharpeRatio,
    /// 年化索提诺比率
    SortinoRatio,
    /// 年化卡尔马比率
    CalmarRatio,
    /// 非年化夏普比率
    SharpeRatioRaw,
    /// 非年化索提诺比率
    SortinoRatioRaw,
    /// 非年化卡尔马比率
    CalmarRatioRaw,
    /// 总回报率
    TotalReturn,
    /// 胜率
    WinRate,
    /// 盈亏比
    ProfitLossRatio,
}

impl OptimizeMetric {
    /// 转换为对应的性能指标键名
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::SharpeRatio => "sharpe_ratio",
            Self::SortinoRatio => "sortino_ratio",
            Self::CalmarRatio => "calmar_ratio",
            Self::SharpeRatioRaw => "sharpe_ratio_raw",
            Self::SortinoRatioRaw => "sortino_ratio_raw",
            Self::CalmarRatioRaw => "calmar_ratio_raw",
            Self::TotalReturn => "total_return",
            Self::WinRate => "win_rate",
            Self::ProfitLossRatio => "profit_loss_ratio",
        }
    }
}

impl<'source> FromPyObject<'source> for OptimizeMetric {
    fn extract_bound(ob: &Bound<'source, PyAny>) -> PyResult<Self> {
        let s: String = ob.extract()?;
        match s.as_str() {
            "sharpe_ratio" => Ok(Self::SharpeRatio),
            "sortino_ratio" => Ok(Self::SortinoRatio),
            "calmar_ratio" => Ok(Self::CalmarRatio),
            "sharpe_ratio_raw" => Ok(Self::SharpeRatioRaw),
            "sortino_ratio_raw" => Ok(Self::SortinoRatioRaw),
            "calmar_ratio_raw" => Ok(Self::CalmarRatioRaw),
            "total_return" => Ok(Self::TotalReturn),
            "win_rate" => Ok(Self::WinRate),
            "profit_loss_ratio" => Ok(Self::ProfitLossRatio),
            _ => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Unknown optimize metric: {}. Valid options: sharpe_ratio, sortino_ratio, calmar_ratio, sharpe_ratio_raw, sortino_ratio_raw, calmar_ratio_raw, total_return, win_rate, profit_loss_ratio",
                s
            ))),
        }
    }
}

#[derive(Debug, Clone, FromPyObject)]
pub struct OptimizerConfig {
    pub explore_ratio: f64,
    pub sigma_ratio: f64,
    pub weight_decay: f64,
    pub top_k_ratio: f64,
    pub samples_per_round: usize,
    /// 最大采样数量
    pub max_samples: usize,
    /// 最小采样数量（至少运行这么多次才会检查停止条件）
    pub min_samples: usize,
    /// 最大迭代轮数
    pub max_rounds: usize,
    /// 停止条件：连续多少轮没有创新高则停止
    pub stop_patience: usize,
    /// 优化目标指标
    pub optimize_metric: OptimizeMetric,
    /// 初始采样点（用于继承先验）
    pub init_samples: Option<Vec<Vec<f64>>>,
}

// 移除 #[pymethods] impl OptimizerConfig

impl Default for OptimizerConfig {
    fn default() -> Self {
        Self {
            explore_ratio: 0.30,
            sigma_ratio: 0.15,
            weight_decay: 0.10,
            top_k_ratio: 0.70,
            samples_per_round: 100,
            max_samples: 10000,
            min_samples: 400,
            max_rounds: 200,
            stop_patience: 10,
            optimize_metric: OptimizeMetric::CalmarRatioRaw,
            init_samples: None,
        }
    }
}
