use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use std::collections::HashMap;

/// 单窗口优化结果
#[derive(Debug, Clone)]
pub struct WindowResult {
    pub window_id: usize,
    pub train_range: (usize, usize),
    pub test_range: (usize, usize),
    /// 最优参数 (indicators层级)
    pub best_params: HashMap<String, HashMap<String, HashMap<String, f64>>>,
    pub train_calmar: f64,
    pub test_calmar: f64,
    /// 样本内总收益 (便于展示)
    pub train_return: f64,
    /// 样本外总收益
    pub test_return: f64,
}

impl<'py> IntoPyObject<'py> for WindowResult {
    type Target = PyDict;
    type Output = Bound<'py, PyDict>;
    type Error = PyErr;

    fn into_pyobject(self, py: Python<'py>) -> Result<Self::Output, Self::Error> {
        let dict = PyDict::new(py);
        dict.set_item("window_id", self.window_id)?;
        dict.set_item("train_range", self.train_range)?; // tuple -> tuple
        dict.set_item("test_range", self.test_range)?;
        dict.set_item("best_params", self.best_params)?;
        dict.set_item("train_calmar", self.train_calmar)?;
        dict.set_item("test_calmar", self.test_calmar)?;
        dict.set_item("train_return", self.train_return)?;
        dict.set_item("test_return", self.test_return)?;
        Ok(dict)
    }
}

/// 整体向前滚动结果
#[derive(Debug, Clone)]
pub struct WalkForwardResult {
    pub windows: Vec<WindowResult>,
    /// 样本外总体平均 Calmar
    pub aggregate_test_calmar: f64,
    pub aggregate_test_return: f64,
}

impl<'py> IntoPyObject<'py> for WalkForwardResult {
    type Target = PyDict;
    type Output = Bound<'py, PyDict>;
    type Error = PyErr;

    fn into_pyobject(self, py: Python<'py>) -> Result<Self::Output, Self::Error> {
        let dict = PyDict::new(py);

        let windows_list = PyList::new(py, self.windows)?;
        dict.set_item("windows", windows_list)?;

        dict.set_item("aggregate_test_calmar", self.aggregate_test_calmar)?;
        dict.set_item("aggregate_test_return", self.aggregate_test_return)?;

        Ok(dict)
    }
}
