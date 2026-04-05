use crate::backtest_engine::backtester::BacktestParamSegment;
use crate::types::{DataPack, OptimizeMetric, ResultPack, SingleParamSet};
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;

/// 下次窗口时间提示（UTC ms）
#[gen_stub_pyclass]
#[pyclass(get_all)]
#[derive(Clone)]
pub struct NextWindowHint {
    pub expected_window_switch_time_ms: i64,
    pub eta_days: f64,
    pub based_on_window_id: usize,
}

/// 窗口级结构性元数据
#[gen_stub_pyclass]
#[pyclass(get_all)]
#[derive(Clone)]
pub struct WindowMeta {
    pub window_id: usize,
    pub best_params: SingleParamSet,
    pub has_cross_boundary_position: bool,
    // 中文注释：这里对外用半开区间 tuple 暴露，语义等价于摘要里的 Range<usize>。
    pub test_active_base_row_range: (usize, usize),
    pub train_warmup_time_range: Option<(i64, i64)>,
    pub train_active_time_range: (i64, i64),
    pub train_pack_time_range: (i64, i64),
    pub test_warmup_time_range: (i64, i64),
    pub test_active_time_range: (i64, i64),
    pub test_pack_time_range: (i64, i64),
}

/// 窗口级完整产物
#[gen_stub_pyclass]
#[pyclass(get_all)]
#[derive(Clone)]
pub struct WindowArtifact {
    pub train_pack_data: DataPack,
    pub test_pack_data: DataPack,
    pub test_pack_result: ResultPack,
    pub meta: WindowMeta,
}

/// 拼接级完整产物
#[gen_stub_pyclass]
#[pyclass(get_all)]
#[derive(Clone)]
pub struct StitchedMeta {
    pub window_count: usize,
    pub stitched_pack_time_range_from_active: (i64, i64),
    pub stitched_window_active_time_ranges: Vec<(i64, i64)>,
    pub backtest_schedule: Vec<BacktestParamSegment>,
    pub next_window_hint: NextWindowHint,
}

/// 拼接级完整产物
#[gen_stub_pyclass]
#[pyclass(get_all)]
#[derive(Clone)]
pub struct StitchedArtifact {
    pub stitched_data: DataPack,
    pub result: ResultPack,
    pub meta: StitchedMeta,
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
