use crate::types::{RoundSummary, SingleParamSet};
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use std::collections::HashMap;

/// 单窗口优化结果
#[gen_stub_pyclass]
#[pyclass(get_all)]
#[derive(Debug, Clone)]
pub struct WindowResult {
    pub window_id: usize,
    pub train_range: (usize, usize),
    pub test_range: (usize, usize),
    /// 最优参数集 (完整结构)
    pub best_params: SingleParamSet,
    /// 优化目标
    pub optimize_metric: String,

    /// 训练集指标
    pub train_metrics: HashMap<String, f64>,
    /// 测试集指标
    pub test_metrics: HashMap<String, f64>,

    // 可选：每轮优化历史（如果需要详细分析）
    pub history: Option<Vec<RoundSummary>>,
}

/// 整体向前滚动结果
#[gen_stub_pyclass]
#[pyclass(get_all)]
#[derive(Debug, Clone)]
pub struct WalkForwardResult {
    pub windows: Vec<WindowResult>,
    pub optimize_metric: String,
    /// 样本外总体平均指标
    pub aggregate_test_metrics: HashMap<String, f64>,
}
