use crate::types::OptimizerConfig;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;

/// 向前滚动优化配置
#[gen_stub_pyclass]
#[pyclass(get_all, set_all)]
#[derive(Debug, Clone)]
pub struct WalkForwardConfig {
    /// 训练窗口长度（固定 bar 数）
    pub train_bars: usize,
    /// 过渡窗口长度（固定 bar 数）
    pub transition_bars: usize,
    /// 测试窗口长度（固定 bar 数）
    pub test_bars: usize,
    /// 是否从上一窗口继承权重先验，默认 true
    pub inherit_prior: bool,
    /// 内嵌的单次优化器配置
    pub optimizer_config: OptimizerConfig,
}

#[gen_stub_pymethods]
#[pymethods]
impl WalkForwardConfig {
    #[new]
    #[pyo3(signature = (*, train_bars, transition_bars, test_bars, inherit_prior=true, optimizer_config=None))]
    pub fn new(
        train_bars: usize,
        transition_bars: usize,
        test_bars: usize,
        inherit_prior: bool,
        optimizer_config: Option<OptimizerConfig>,
    ) -> Self {
        Self {
            train_bars,
            transition_bars,
            test_bars,
            inherit_prior,
            optimizer_config: optimizer_config.unwrap_or_default(),
        }
    }
}

impl Default for WalkForwardConfig {
    fn default() -> Self {
        // 中文注释：默认使用固定 bar 口径，避免随总样本增长导致窗口漂移。
        Self::new(500, 100, 200, true, None)
    }
}
