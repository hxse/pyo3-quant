use crate::types::OptimizerConfig;
use pyo3::prelude::*;

/// 向前滚动优化配置
#[derive(Debug, Clone, FromPyObject)]
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

impl Default for WalkForwardConfig {
    fn default() -> Self {
        Self {
            train_ratio: 0.60,
            test_ratio: 0.20,
            step_ratio: 0.10,
            inherit_prior: true,
            optimizer_config: OptimizerConfig::default(),
        }
    }
}
