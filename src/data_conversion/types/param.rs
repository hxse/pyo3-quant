use pyo3::prelude::*;

#[derive(Debug, Clone, FromPyObject)]
#[allow(dead_code)]
pub struct Param {
    /// 当前参数值
    pub value: f64,
    /// 参数初始值，用于重置或恢复默认配置
    pub initial_value: f64,
    /// 参数最小值限制
    pub min: f64,
    /// 参数初始最小值，用于重置或恢复默认配置
    pub initial_min: f64,
    /// 参数最大值限制
    pub max: f64,
    /// 参数初始最大值，用于重置或恢复默认配置
    pub initial_max: f64,
    /// 参数步长，用于优化时的增量调整
    pub step: f64,
    /// 参数初始步长，用于重置或恢复默认配置
    pub initial_step: f64,
    /// 是否开启参数优化，在参数优化过程中使用
    pub optimize: bool,
    /// 是否开启对数分布，用于参数优化时的采样策略
    pub log_scale: bool,
}
