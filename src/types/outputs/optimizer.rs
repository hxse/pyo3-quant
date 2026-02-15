use crate::types::inputs::optimizer::OptimizeMetric;
use crate::types::SingleParamSet;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use std::collections::HashMap;

/// 采样点结构
#[gen_stub_pyclass]
#[pyclass(get_all)]
#[derive(Clone, Debug)]
pub struct SamplePoint {
    /// 各维度的参数值
    pub values: Vec<f64>,
    /// 该参数组合的目标指标值（由 optimize_metric 指定）
    pub metric_value: f64,
    /// 所有已计算的性能指标
    pub all_metrics: HashMap<String, f64>,
}

#[gen_stub_pyclass]
#[pyclass(get_all)]
#[derive(Debug, Clone)]
pub struct RoundSummary {
    pub round: usize,
    pub best_value: f64,
    pub median_value: f64,
    pub sample_count: usize,
}

#[gen_stub_pyclass]
#[pyclass(get_all)]
#[derive(Debug, Clone)]
pub struct OptimizationResult {
    /// 最优参数集 (完整结构，value 已更新)
    pub best_params: SingleParamSet,
    /// 优化目标
    pub optimize_metric: OptimizeMetric,
    pub optimize_value: f64,
    /// 所有计算的性能指标
    pub metrics: HashMap<String, f64>,
    /// 统计
    pub total_samples: usize,
    pub rounds: usize,
    pub history: Vec<RoundSummary>,
    /// Top K 参数集 (用于 WF 热启动)
    pub top_k_params: Vec<SingleParamSet>,

    // Internal use (for debugging)
    pub top_k_samples: Vec<SamplePoint>,
}
