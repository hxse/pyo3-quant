use crate::types::{RoundSummary, SingleParamSet};
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use std::collections::HashMap;

/// 单窗口优化结果
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

impl<'py> IntoPyObject<'py> for WindowResult {
    type Target = PyDict;
    type Output = Bound<'py, PyDict>;
    type Error = PyErr;

    fn into_pyobject(self, py: Python<'py>) -> Result<Self::Output, Self::Error> {
        let dict = PyDict::new(py);
        dict.set_item("window_id", self.window_id)?;
        dict.set_item("train_range", self.train_range)?;
        dict.set_item("test_range", self.test_range)?;
        dict.set_item("best_params", self.best_params)?;
        dict.set_item("optimize_metric", self.optimize_metric)?;
        dict.set_item("train_metrics", self.train_metrics)?;
        dict.set_item("test_metrics", self.test_metrics)?;

        if let Some(history) = self.history {
            let history_list = PyList::new(py, history)?;
            dict.set_item("history", history_list)?;
        } else {
            dict.set_item("history", py.None())?;
        }

        Ok(dict)
    }
}

/// 整体向前滚动结果
#[derive(Debug, Clone)]
pub struct WalkForwardResult {
    pub windows: Vec<WindowResult>,
    pub optimize_metric: String,
    /// 样本外总体平均指标
    pub aggregate_test_metrics: HashMap<String, f64>,
}

impl<'py> IntoPyObject<'py> for WalkForwardResult {
    type Target = PyDict;
    type Output = Bound<'py, PyDict>;
    type Error = PyErr;

    fn into_pyobject(self, py: Python<'py>) -> Result<Self::Output, Self::Error> {
        let dict = PyDict::new(py);

        let windows_list = PyList::new(py, self.windows)?;
        dict.set_item("windows", windows_list)?;

        dict.set_item("optimize_metric", self.optimize_metric)?;
        dict.set_item("aggregate_test_metrics", self.aggregate_test_metrics)?;

        Ok(dict)
    }
}
