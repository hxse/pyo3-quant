use crate::types::OptimizerConfig;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;

/// 向前滚动优化配置
#[gen_stub_pyclass]
#[pyclass(get_all, set_all)]
#[derive(Debug, Clone)]
pub struct WalkForwardConfig {
    /// 训练窗口长度（占总数据的比例），默认 0.60
    pub train_ratio: f64,
    /// 测试窗口长度（占总数据的比例），默认 0.20
    pub test_ratio: f64,
    /// 滚动步长（占总数据的比例），默认 0.10
    pub step_ratio: f64,
    /// 是否从上一窗口继承权重先验，默认 true
    pub inherit_prior: bool,
    /// 内嵌的单次优化器配置
    pub optimizer_config: OptimizerConfig,
}

#[gen_stub_pymethods]
#[pymethods]
impl WalkForwardConfig {
    #[new]
    #[pyo3(signature = (*, train_ratio=0.60, test_ratio=0.20, step_ratio=0.10, inherit_prior=true, optimizer_config=None))]
    pub fn new(
        train_ratio: f64,
        test_ratio: f64,
        step_ratio: f64,
        inherit_prior: bool,
        optimizer_config: Option<OptimizerConfig>,
    ) -> Self {
        Self {
            train_ratio,
            test_ratio,
            step_ratio,
            inherit_prior,
            optimizer_config: optimizer_config.unwrap_or_default(),
        }
    }
}

impl Default for WalkForwardConfig {
    fn default() -> Self {
        Self::new(0.60, 0.20, 0.10, true, None)
    }
}
