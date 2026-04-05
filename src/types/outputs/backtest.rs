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
    #[new]
    #[pyo3(signature = (mapping, ranges, base_data_key, performance=None, indicators=None, signals=None, backtest_result=None))]
    pub fn new(
        py: Python<'_>,
        mapping: Bound<'_, PyAny>,
        ranges: HashMap<String, Py<SourceRange>>,
        base_data_key: String,
        performance: Option<PerformanceMetrics>,
        indicators: Option<HashMap<String, Bound<'_, PyAny>>>,
        signals: Option<Bound<'_, PyAny>>,
        backtest_result: Option<Bound<'_, PyAny>>,
    ) -> PyResult<Self> {
        let indicators_inner = match indicators {
            Some(map) => {
                let mut inner = HashMap::new();
                for (key, value) in map {
                    let df: PyDataFrame = value.extract()?;
                    inner.insert(key, df.into());
                }
                Some(inner)
            }
            None => None,
        };
        let signals_inner = match signals {
            Some(value) => {
                let df: PyDataFrame = value.extract()?;
                Some(df.into())
            }
            None => None,
        };
        let backtest_inner = match backtest_result {
            Some(value) => {
                let df: PyDataFrame = value.extract()?;
                Some(df.into())
            }
            None => None,
        };
        let mapping_df: PyDataFrame = mapping.extract()?;
        let mut ranges_inner = HashMap::new();
        for (key, value) in ranges {
            ranges_inner.insert(key, value.bind(py).borrow().clone());
        }
        Ok(Self {
            indicators: indicators_inner,
            signals: signals_inner,
            backtest: backtest_inner,
            performance,
            mapping: mapping_df.into(),
            ranges: ranges_inner,
            base_data_key,
        })
    }

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

    #[setter]
    pub fn set_indicators(
        &mut self,
        value: Option<HashMap<String, Bound<'_, PyAny>>>,
    ) -> PyResult<()> {
        self.indicators = match value {
            Some(map) => {
                let mut inner = HashMap::new();
                for (key, item) in map {
                    let df: PyDataFrame = item.extract()?;
                    inner.insert(key, df.into());
                }
                Some(inner)
            }
            None => None,
        };
        Ok(())
    }

    #[setter]
    pub fn set_signals(&mut self, value: Option<Bound<'_, PyAny>>) -> PyResult<()> {
        self.signals = match value {
            Some(item) => {
                let df: PyDataFrame = item.extract()?;
                Some(df.into())
            }
            None => None,
        };
        Ok(())
    }

    #[setter]
    pub fn set_backtest_result(&mut self, value: Option<Bound<'_, PyAny>>) -> PyResult<()> {
        self.backtest = match value {
            Some(item) => {
                let df: PyDataFrame = item.extract()?;
                Some(df.into())
            }
            None => None,
        };
        Ok(())
    }

    #[setter]
    pub fn set_mapping(&mut self, value: Bound<'_, PyAny>) -> PyResult<()> {
        let df: PyDataFrame = value.extract()?;
        self.mapping = df.into();
        Ok(())
    }

    #[setter]
    pub fn set_performance(&mut self, value: Option<PerformanceMetrics>) {
        self.performance = value;
    }

    #[setter]
    pub fn set_base_data_key(&mut self, value: String) {
        self.base_data_key = value;
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
