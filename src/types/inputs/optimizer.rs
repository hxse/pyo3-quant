use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use pyo3_stub_gen::PyStubType;

/// 基准函数枚举
#[pyclass(eq, eq_int, hash, frozen)]
#[derive(Clone, Copy, Debug, PartialEq, Eq, Hash)]
pub enum BenchmarkFunction {
    Sphere,
    Rosenbrock,
    Rastrigin,
    Ackley,
}

impl BenchmarkFunction {
    pub fn evaluate(&self, x: &[f64]) -> f64 {
        match self {
            Self::Sphere => x.iter().map(|&v| v * v).sum(),
            Self::Rosenbrock => {
                let mut sum = 0.0;
                for i in 0..x.len() - 1 {
                    let term1 = x[i + 1] - x[i] * x[i];
                    let term2 = 1.0 - x[i];
                    sum += 100.0 * term1 * term1 + term2 * term2;
                }
                sum
            }
            Self::Rastrigin => {
                let a = 10.0;
                let n = x.len() as f64;
                a * n
                    + x.iter()
                        .map(|&v| v * v - a * (2.0 * std::f64::consts::PI * v).cos())
                        .sum::<f64>()
            }
            Self::Ackley => {
                let n = x.len() as f64;
                let sum1: f64 = x.iter().map(|&v| v * v).sum();
                let sum2: f64 = x
                    .iter()
                    .map(|&v| (2.0 * std::f64::consts::PI * v).cos())
                    .sum();
                -20.0 * (-0.2 * (sum1 / n).sqrt()).exp() - (sum2 / n).exp()
                    + 20.0
                    + std::f64::consts::E
            }
        }
    }
}

#[gen_stub_pymethods]
#[pymethods]
impl BenchmarkFunction {
    /// 返回枚举变体名（用于展示/日志）
    pub fn name(&self) -> &'static str {
        match self {
            Self::Sphere => "Sphere",
            Self::Rosenbrock => "Rosenbrock",
            Self::Rastrigin => "Rastrigin",
            Self::Ackley => "Ackley",
        }
    }

    /// 返回稳定的业务键名（用于程序逻辑）
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Sphere => "sphere",
            Self::Rosenbrock => "rosenbrock",
            Self::Rastrigin => "rastrigin",
            Self::Ackley => "ackley",
        }
    }

    fn __str__(&self) -> String {
        self.name().to_string()
    }

    fn __repr__(&self) -> String {
        format!("BenchmarkFunction.{}", self.name())
    }
}

impl PyStubType for BenchmarkFunction {
    fn type_output() -> pyo3_stub_gen::TypeInfo {
        pyo3_stub_gen::TypeInfo::locally_defined(
            "BenchmarkFunction",
            pyo3_stub_gen::ModuleRef::Default,
        )
    }
}

pyo3_stub_gen::inventory::submit! {
    pyo3_stub_gen::type_info::PyEnumInfo {
        enum_id: || std::any::TypeId::of::<BenchmarkFunction>(),
        pyclass_name: "BenchmarkFunction",
        module: Some("pyo3_quant._pyo3_quant"),
        doc: "基准函数枚举",
        variants: &[
            ("Sphere", "Sphere"),
            ("Rosenbrock", "Rosenbrock"),
            ("Rastrigin", "Rastrigin"),
            ("Ackley", "Ackley"),
        ],
    }
}

/// 优化目标指标枚举
#[pyclass(eq, eq_int, hash, frozen)]
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
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
    /// 最大回撤
    MaxDrawdown,
}

#[gen_stub_pymethods]
#[pymethods]
impl OptimizeMetric {
    /// 返回枚举变体名（用于展示/日志）
    pub fn name(&self) -> &'static str {
        match self {
            Self::SharpeRatio => "SharpeRatio",
            Self::SortinoRatio => "SortinoRatio",
            Self::CalmarRatio => "CalmarRatio",
            Self::SharpeRatioRaw => "SharpeRatioRaw",
            Self::SortinoRatioRaw => "SortinoRatioRaw",
            Self::CalmarRatioRaw => "CalmarRatioRaw",
            Self::ProfitLossRatio => "ProfitLossRatio",
            Self::WinRate => "WinRate",
            Self::MaxDrawdown => "MaxDrawdown",
            Self::TotalReturn => "TotalReturn",
        }
    }

    /// 转换为对应的性能指标键名
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::SharpeRatio => "sharpe_ratio",
            Self::SortinoRatio => "sortino_ratio",
            Self::CalmarRatio => "calmar_ratio",
            Self::SharpeRatioRaw => "sharpe_ratio_raw",
            Self::SortinoRatioRaw => "sortino_ratio_raw",
            Self::CalmarRatioRaw => "calmar_ratio_raw",
            Self::ProfitLossRatio => "profit_loss_ratio",
            Self::WinRate => "win_rate",
            Self::MaxDrawdown => "max_drawdown",
            Self::TotalReturn => "total_return",
        }
    }

    fn __str__(&self) -> String {
        self.name().to_string()
    }

    fn __repr__(&self) -> String {
        format!("OptimizeMetric.{}", self.name())
    }
}

impl PyStubType for OptimizeMetric {
    fn type_output() -> pyo3_stub_gen::TypeInfo {
        pyo3_stub_gen::TypeInfo::locally_defined(
            "OptimizeMetric",
            pyo3_stub_gen::ModuleRef::Default,
        )
    }
}

pyo3_stub_gen::inventory::submit! {
    pyo3_stub_gen::type_info::PyEnumInfo {
        enum_id: || std::any::TypeId::of::<OptimizeMetric>(),
        pyclass_name: "OptimizeMetric",
        module: Some("pyo3_quant._pyo3_quant"),
        doc: "优化目标指标枚举",
        variants: &[
            ("SharpeRatio", "年化夏普比率"),
            ("SortinoRatio", "年化索提诺比率"),
            ("CalmarRatio", "年化卡尔马比率"),
            ("SharpeRatioRaw", "非年化夏普比率"),
            ("SortinoRatioRaw", "非年化索提诺比率"),
            ("CalmarRatioRaw", "非年化卡尔马比率"),
            ("TotalReturn", "总回报率"),
            ("WinRate", "胜率"),
            ("ProfitLossRatio", "盈亏比"),
            ("MaxDrawdown", "最大回撤"),
        ],
    }
}

#[gen_stub_pyclass]
#[pyclass(get_all, set_all)]
#[derive(Debug, Clone)]
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
    /// 初始采样点（用于热启动）
    pub init_samples: Option<Vec<Vec<f64>>>,
    /// 返回 Top K 参数集数量 (0 = 不返回)
    pub return_top_k: usize,
    /// 随机种子（None 表示使用系统随机源）
    pub seed: Option<u64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl OptimizerConfig {
    #[new]
    #[pyo3(signature = (*, explore_ratio=0.20, sigma_ratio=0.10, weight_decay=0.15, top_k_ratio=0.70, samples_per_round=100, max_samples=10000, min_samples=400, max_rounds=200, stop_patience=10, optimize_metric=crate::types::OptimizeMetric::CalmarRatioRaw, init_samples=None, return_top_k=10, seed=None))]
    #[allow(clippy::too_many_arguments)]
    pub fn new(
        explore_ratio: f64,
        sigma_ratio: f64,
        weight_decay: f64,
        top_k_ratio: f64,
        samples_per_round: usize,
        max_samples: usize,
        min_samples: usize,
        max_rounds: usize,
        stop_patience: usize,
        optimize_metric: crate::types::OptimizeMetric,
        init_samples: Option<Vec<Vec<f64>>>,
        return_top_k: usize,
        seed: Option<u64>,
    ) -> Self {
        Self {
            explore_ratio,
            sigma_ratio,
            weight_decay,
            top_k_ratio,
            samples_per_round,
            max_samples,
            min_samples,
            max_rounds,
            stop_patience,
            optimize_metric,
            init_samples,
            return_top_k,
            seed,
        }
    }
}

impl Default for OptimizerConfig {
    fn default() -> Self {
        Self::new(
            0.20,
            0.10,
            0.15,
            0.70,
            100,
            10000,
            400,
            200,
            10,
            crate::types::OptimizeMetric::CalmarRatioRaw,
            None,
            10,
            None,
        )
    }
}
