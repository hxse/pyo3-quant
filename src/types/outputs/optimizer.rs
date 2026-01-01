use crate::backtest_engine::optimizer::optimizer_core::SamplePoint;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use std::collections::HashMap;

#[derive(Debug, Clone)]
pub struct RoundSummary {
    pub round: usize,
    pub best_calmar: f64,
    pub median_calmar: f64,
    pub sample_count: usize,
}

impl<'py> IntoPyObject<'py> for RoundSummary {
    type Target = PyDict;
    type Output = Bound<'py, PyDict>;
    type Error = PyErr;

    fn into_pyobject(self, py: Python<'py>) -> Result<Self::Output, Self::Error> {
        let dict = PyDict::new(py);
        dict.set_item("round", self.round)?;
        dict.set_item("best_calmar", self.best_calmar)?;
        dict.set_item("median_calmar", self.median_calmar)?;
        dict.set_item("sample_count", self.sample_count)?;
        Ok(dict)
    }
}

#[derive(Debug, Clone)]
pub struct OptimizationResult {
    pub best_params: HashMap<String, HashMap<String, HashMap<String, f64>>>, // indicators 路径格式
    pub best_signal_params: HashMap<String, f64>,
    pub best_backtest_params: HashMap<String, f64>,
    pub best_calmar: f64,
    pub total_samples: usize,
    pub rounds: usize,
    pub history: Vec<RoundSummary>,

    // 以下字段用于 Walk Forward 继承，对 Python 隐藏
    pub best_sample_values: Option<Vec<f64>>,
    pub top_k_samples: Vec<SamplePoint>,
}

impl<'py> IntoPyObject<'py> for OptimizationResult {
    type Target = PyDict;
    type Output = Bound<'py, PyDict>;
    type Error = PyErr;

    fn into_pyobject(self, py: Python<'py>) -> Result<Self::Output, Self::Error> {
        let dict = PyDict::new(py);
        dict.set_item("best_params", self.best_params)?;
        dict.set_item("best_signal_params", self.best_signal_params)?;
        dict.set_item("best_backtest_params", self.best_backtest_params)?;
        dict.set_item("best_calmar", self.best_calmar)?;
        dict.set_item("total_samples", self.total_samples)?;
        dict.set_item("rounds", self.rounds)?;

        // 转换 history list
        let history_list = PyList::new(py, self.history)?;
        dict.set_item("history", history_list)?;

        Ok(dict)
    }
}
