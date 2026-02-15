use crate::types::OptimizeMetric;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;

/// 敏感性测试配置
#[gen_stub_pyclass]
#[pyclass(get_all, set_all)]
#[derive(Debug, Clone)]
pub struct SensitivityConfig {
    /// 抖动比例 (例如 0.05 代表 +/- 5%)
    pub jitter_ratio: f64,
    /// 采样次数
    pub n_samples: usize,
    /// 分布类型: "uniform" (默认) 或 "normal"
    pub distribution: String,
    /// 随机种子 (保证可复现)
    pub seed: Option<u64>,
    /// 评价指标 (默认 CalmarRatioRaw)
    pub metric: OptimizeMetric,
}

#[gen_stub_pymethods]
#[pymethods]
impl SensitivityConfig {
    #[new]
    #[pyo3(signature = (*, jitter_ratio=0.05, n_samples=100, distribution="uniform".to_string(), seed=None, metric=OptimizeMetric::CalmarRatioRaw))]
    pub fn new(
        jitter_ratio: f64,
        n_samples: usize,
        distribution: String,
        seed: Option<u64>,
        metric: OptimizeMetric,
    ) -> Self {
        Self {
            jitter_ratio,
            n_samples,
            distribution,
            seed,
            metric,
        }
    }
}

impl Default for SensitivityConfig {
    fn default() -> Self {
        Self::new(
            0.05,
            100,
            "uniform".to_string(),
            None,
            OptimizeMetric::CalmarRatioRaw,
        )
    }
}
