use crate::types::OptimizeMetric;
use pyo3::prelude::*;
use std::collections::HashMap;

/// 敏感性测试配置
#[derive(Debug, Clone, FromPyObject)]
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

impl Default for SensitivityConfig {
    fn default() -> Self {
        Self {
            jitter_ratio: 0.05,
            n_samples: 100,
            distribution: "uniform".to_string(),
            seed: None,
            metric: OptimizeMetric::CalmarRatioRaw,
        }
    }
}

/// 单个样本的测试结果
#[derive(Debug, Clone)]
pub struct SensitivitySample {
    /// 采样后的参数值
    pub values: Vec<f64>,
    /// 目标指标值
    pub metric_value: f64,
    /// 所有性能指标
    pub all_metrics: HashMap<String, f64>,
}

impl<'py> IntoPyObject<'py> for SensitivitySample {
    type Target = pyo3::types::PyDict;
    type Output = Bound<'py, pyo3::types::PyDict>;
    type Error = PyErr;

    fn into_pyobject(self, py: Python<'py>) -> Result<Self::Output, Self::Error> {
        let dict = pyo3::types::PyDict::new(py);
        dict.set_item("values", self.values)?;
        dict.set_item("metric_value", self.metric_value)?;
        dict.set_item("all_metrics", self.all_metrics)?;
        Ok(dict)
    }
}

/// 敏感性测试总结果
#[derive(Debug, Clone)]
pub struct SensitivityResult {
    pub target_metric: String,
    pub original_value: f64,
    pub samples: Vec<SensitivitySample>,

    // 统计量
    pub mean: f64,
    pub std: f64,
    pub min: f64,
    pub max: f64,
    pub median: f64,
    pub cv: f64, // 变异系数 (std / mean)
}

impl<'py> IntoPyObject<'py> for SensitivityResult {
    type Target = pyo3::types::PyDict;
    type Output = Bound<'py, pyo3::types::PyDict>;
    type Error = PyErr;

    fn into_pyobject(self, py: Python<'py>) -> Result<Self::Output, Self::Error> {
        let dict = pyo3::types::PyDict::new(py);
        dict.set_item("target_metric", self.target_metric)?;
        dict.set_item("original_value", self.original_value)?;
        dict.set_item("samples", self.samples)?;
        dict.set_item("mean", self.mean)?;
        dict.set_item("std", self.std)?;
        dict.set_item("min", self.min)?;
        dict.set_item("max", self.max)?;
        dict.set_item("median", self.median)?;
        dict.set_item("cv", self.cv)?;
        Ok(dict)
    }
}
