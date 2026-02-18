use crate::types::{OptimizeMetric, RoundSummary, SingleParamSet};
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
    pub transition_range: (usize, usize),
    pub test_range: (usize, usize),
    /// 最优参数集 (完整结构)
    pub best_params: SingleParamSet,
    /// 优化目标
    pub optimize_metric: OptimizeMetric,

    /// 训练集指标
    pub train_metrics: HashMap<String, f64>,
    /// 测试集指标
    pub test_metrics: HashMap<String, f64>,
    /// 训练/测试指标差值（train - test）
    pub train_test_gap_metrics: HashMap<String, f64>,
    /// 当前窗口测试期逐 bar 时间戳（UTC ms）
    pub test_times: Vec<i64>,
    /// 当前窗口测试期逐 bar 收益率序列
    pub test_returns: Vec<f64>,

    // 可选：每轮优化历史（如果需要详细分析）
    pub history: Option<Vec<RoundSummary>>,
}

/// 统计分布摘要
#[gen_stub_pyclass]
#[pyclass(get_all)]
#[derive(Debug, Clone)]
pub struct MetricDistributionStats {
    pub mean: f64,
    pub median: f64,
    pub std: f64,
    pub min: f64,
    pub max: f64,
    pub p05: f64,
    pub p95: f64,
}

/// 整体向前滚动结果
#[gen_stub_pyclass]
#[pyclass(get_all)]
#[derive(Debug, Clone)]
pub struct WalkForwardResult {
    pub windows: Vec<WindowResult>,
    pub optimize_metric: OptimizeMetric,
    /// 样本外总体指标（基于拼接后的 OOS equity 曲线）
    pub aggregate_test_metrics: HashMap<String, f64>,
    /// 窗口级测试指标分布统计
    pub window_metric_stats: HashMap<String, MetricDistributionStats>,
    /// 拼接后样本外资金曲线时间轴（UTC ms）
    pub stitched_time: Vec<i64>,
    /// 拼接后样本外资金曲线（起点固定为 1.0）
    pub stitched_equity: Vec<f64>,
    /// 测试集表现最优窗口 ID
    pub best_window_id: usize,
    /// 测试集表现最差窗口 ID
    pub worst_window_id: usize,
}
