use polars::prelude::*;
use pyo3::prelude::*;
use pyo3::IntoPyObjectExt;
use pyo3_polars::PyDataFrame;
use pyo3_stub_gen::derive::*;
use std::collections::HashMap;

use crate::types::SourceRange;

pub type PerformanceMetrics = HashMap<String, f64>;
pub type IndicatorResults = HashMap<String, DataFrame>;

#[gen_stub_pyclass]
#[pyclass]
#[derive(Debug, Clone, Default)]
pub struct ResultPack {
    pub(crate) indicators: Option<IndicatorResults>,
    pub(crate) signals: Option<DataFrame>,
    pub(crate) backtest: Option<DataFrame>,
    pub(crate) performance: Option<PerformanceMetrics>,
    pub(crate) mapping: DataFrame,
    pub(crate) ranges: HashMap<String, SourceRange>,
    pub(crate) base_data_key: String,
}

#[gen_stub_pymethods]
#[pymethods]
impl ResultPack {
    #[getter]
    pub fn indicators<'py>(
        &self,
        py: Python<'py>,
    ) -> PyResult<Option<Bound<'py, pyo3::types::PyDict>>> {
        match &self.indicators {
            Some(map) => {
                let dict = pyo3::types::PyDict::new(py);
                for (k, v) in map {
                    dict.set_item(k, PyDataFrame(v.clone()))?;
                }
                Ok(Some(dict))
            }
            None => Ok(None),
        }
    }

    #[getter]
    pub fn signals<'py>(&self, py: Python<'py>) -> PyResult<Option<Bound<'py, PyAny>>> {
        match &self.signals {
            Some(df) => Ok(Some(PyDataFrame(df.clone()).into_bound_py_any(py)?)),
            None => Ok(None),
        }
    }

    #[getter]
    pub fn backtest_result<'py>(&self, py: Python<'py>) -> PyResult<Option<Bound<'py, PyAny>>> {
        match &self.backtest {
            Some(df) => Ok(Some(PyDataFrame(df.clone()).into_bound_py_any(py)?)),
            None => Ok(None),
        }
    }

    #[getter]
    pub fn mapping<'py>(&self, py: Python<'py>) -> PyResult<Bound<'py, PyAny>> {
        PyDataFrame(self.mapping.clone()).into_bound_py_any(py)
    }

    #[getter]
    pub fn ranges(&self, py: Python<'_>) -> PyResult<HashMap<String, Py<SourceRange>>> {
        let mut py_map = HashMap::new();
        for (key, value) in &self.ranges {
            py_map.insert(key.clone(), Py::new(py, value.clone())?);
        }
        Ok(py_map)
    }

    #[getter]
    pub fn performance(&self) -> Option<PerformanceMetrics> {
        self.performance.clone()
    }

    #[getter]
    pub fn base_data_key(&self) -> String {
        self.base_data_key.clone()
    }
}

impl ResultPack {
    /// 中文注释：A2 先提供只读 checked 构造，完整规则统一由 builder 收口。
    pub fn new_checked(
        indicators: Option<IndicatorResults>,
        signals: Option<DataFrame>,
        backtest: Option<DataFrame>,
        performance: Option<PerformanceMetrics>,
        mapping: DataFrame,
        ranges: HashMap<String, SourceRange>,
        base_data_key: String,
    ) -> Self {
        Self {
            indicators,
            signals,
            backtest,
            performance,
            mapping,
            ranges,
            base_data_key,
        }
    }
}
