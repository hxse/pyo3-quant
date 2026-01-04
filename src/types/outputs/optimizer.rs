use crate::backtest_engine::optimizer::optimizer_core::SamplePoint;
use crate::types::SingleParamSet;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use std::collections::HashMap;

#[derive(Debug, Clone)]
pub struct RoundSummary {
    pub round: usize,
    pub best_value: f64,
    pub median_value: f64,
    pub sample_count: usize,
}

impl<'py> IntoPyObject<'py> for RoundSummary {
    type Target = PyDict;
    type Output = Bound<'py, PyDict>;
    type Error = PyErr;

    fn into_pyobject(self, py: Python<'py>) -> Result<Self::Output, Self::Error> {
        let dict = PyDict::new(py);
        dict.set_item("round", self.round)?;
        dict.set_item("best_value", self.best_value)?;
        dict.set_item("median_value", self.median_value)?;
        dict.set_item("sample_count", self.sample_count)?;
        Ok(dict)
    }
}

impl<'py> IntoPyObject<'py> for SamplePoint {
    type Target = PyDict;
    type Output = Bound<'py, PyDict>;
    type Error = PyErr;

    fn into_pyobject(self, py: Python<'py>) -> Result<Self::Output, Self::Error> {
        let dict = PyDict::new(py);
        dict.set_item("values", self.values)?;
        dict.set_item("metric_value", self.metric_value)?;
        dict.set_item("all_metrics", self.all_metrics)?;
        Ok(dict)
    }
}

#[derive(Debug, Clone)]
pub struct OptimizationResult {
    /// 最优参数集 (完整结构，value 已更新)
    pub best_params: SingleParamSet,
    /// 优化目标
    pub optimize_metric: String,
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

impl<'py> IntoPyObject<'py> for OptimizationResult {
    type Target = PyDict;
    type Output = Bound<'py, PyDict>;
    type Error = PyErr;

    fn into_pyobject(self, py: Python<'py>) -> Result<Self::Output, Self::Error> {
        let dict = PyDict::new(py);

        // SingleParamSet implements IntoPyObject
        dict.set_item("best_params", self.best_params)?;

        dict.set_item("optimize_metric", self.optimize_metric)?;
        dict.set_item("optimize_value", self.optimize_value)?;
        dict.set_item("metrics", self.metrics)?;
        dict.set_item("total_samples", self.total_samples)?;
        dict.set_item("rounds", self.rounds)?;

        // Rounds
        let history_list = PyList::new(py, self.history)?;
        dict.set_item("history", history_list)?;

        // Top K Params
        let top_k_params_list = PyList::new(py, self.top_k_params)?;
        dict.set_item("top_k_params", top_k_params_list)?;

        // Internal
        let top_k_samples_list = PyList::new(py, self.top_k_samples)?;
        dict.set_item("top_k_samples", top_k_samples_list)?;

        Ok(dict)
    }
}
