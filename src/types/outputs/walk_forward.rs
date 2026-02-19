use crate::types::{BacktestSummary, DataContainer, OptimizeMetric, SingleParamSet};
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;

/// 下次窗口时间提示（UTC ms）
#[gen_stub_pyclass]
#[pyclass(get_all)]
#[derive(Clone)]
pub struct NextWindowHint {
    pub expected_train_start_time_ms: i64,
    pub expected_transition_start_time_ms: i64,
    pub expected_test_start_time_ms: i64,
    pub expected_test_end_time_ms: i64,
    pub expected_window_ready_time_ms: i64,
    pub eta_days: f64,
    pub based_on_window_id: usize,
}

/// 窗口级完整产物
#[gen_stub_pyclass]
#[pyclass(get_all)]
#[derive(Clone)]
pub struct WindowArtifact {
    // CorePayload
    pub data: DataContainer,
    pub summary: BacktestSummary,
    // RangeIdentity
    pub time_range: (i64, i64),
    pub bar_range: (usize, usize),
    pub span_ms: i64,
    pub span_days: f64,
    pub span_months: f64,
    pub bars: usize,
    // WindowContext
    pub window_id: usize,
    pub train_range: (usize, usize),
    pub transition_range: (usize, usize),
    pub test_range: (usize, usize),
    pub best_params: SingleParamSet,
    pub optimize_metric: OptimizeMetric,
    pub has_cross_boundary_position: bool,
}

/// 拼接级完整产物
#[gen_stub_pyclass]
#[pyclass(get_all)]
#[derive(Clone)]
pub struct StitchedArtifact {
    // CorePayload
    pub data: DataContainer,
    pub summary: BacktestSummary,
    // RangeIdentity
    pub time_range: (i64, i64),
    pub bar_range: (usize, usize),
    pub span_ms: i64,
    pub span_days: f64,
    pub span_months: f64,
    pub bars: usize,
    // StitchContext
    pub window_count: usize,
    pub first_test_time_ms: i64,
    pub last_test_time_ms: i64,
    // ScheduleHint
    pub rolling_every_days: f64,
    pub next_window_hint: NextWindowHint,
}

/// 向前测试完整结果（破坏性更新）
#[gen_stub_pyclass]
#[pyclass(get_all)]
#[derive(Clone)]
pub struct WalkForwardResult {
    pub optimize_metric: OptimizeMetric,
    pub window_results: Vec<WindowArtifact>,
    pub stitched_result: StitchedArtifact,
}
