use polars::prelude::*;
use pyo3::prelude::*;
use pyo3::IntoPyObjectExt;
use pyo3_polars::PyDataFrame;
use pyo3_stub_gen::derive::*;
use std::collections::HashMap;

pub type PerformanceMetrics = HashMap<String, f64>;
pub type IndicatorResults = HashMap<String, DataFrame>;

// 为解决 Option<DataFrame> 不满足 PyStubType 的问题，我们将字段改为 pub(crate)
// 并明确指定 getters 的 stub 类型（通过 gen_stub_pymethods）
#[gen_stub_pyclass]
#[pyclass]
#[derive(Debug, Clone, Default)]
pub struct BacktestSummary {
    pub(crate) indicators: Option<IndicatorResults>,
    pub(crate) signals: Option<DataFrame>,
    /// Python getter: `backtest_result`
    pub(crate) backtest: Option<DataFrame>,
    pub(crate) performance: Option<PerformanceMetrics>,
}

#[gen_stub_pymethods]
#[pymethods]
impl BacktestSummary {
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

    #[new]
    #[pyo3(signature = (performance=None, indicators=None, signals=None, backtest_result=None))]
    pub fn new(
        performance: Option<PerformanceMetrics>,
        indicators: Option<HashMap<String, Bound<'_, PyAny>>>,
        signals: Option<Bound<'_, PyAny>>,
        backtest_result: Option<Bound<'_, PyAny>>,
    ) -> PyResult<Self> {
        let indicators_inner = match indicators {
            Some(map) => {
                let mut inner = HashMap::new();
                for (k, v) in map {
                    let df: PyDataFrame = v.extract()?;
                    inner.insert(k, df.into());
                }
                Some(inner)
            }
            None => None,
        };

        let signals_inner = match signals {
            Some(v) => {
                let df: PyDataFrame = v.extract()?;
                Some(df.into())
            }
            None => None,
        };

        let backtest_inner = match backtest_result {
            Some(v) => {
                let df: PyDataFrame = v.extract()?;
                Some(df.into())
            }
            None => None,
        };

        Ok(Self {
            indicators: indicators_inner,
            signals: signals_inner,
            backtest: backtest_inner,
            performance,
        })
    }

    #[setter]
    pub fn set_performance(&mut self, value: Option<PerformanceMetrics>) {
        self.performance = value;
    }

    #[setter]
    pub fn set_indicators(
        &mut self,
        value: Option<HashMap<String, Bound<'_, PyAny>>>,
    ) -> PyResult<()> {
        self.indicators = match value {
            Some(map) => {
                let mut inner = HashMap::new();
                for (k, v) in map {
                    let df: PyDataFrame = v.extract()?;
                    inner.insert(k, df.into());
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
            Some(v) => {
                let df: PyDataFrame = v.extract()?;
                Some(df.into())
            }
            None => None,
        };
        Ok(())
    }

    #[setter]
    pub fn set_backtest_result(&mut self, value: Option<Bound<'_, PyAny>>) -> PyResult<()> {
        self.backtest = match value {
            Some(v) => {
                let df: PyDataFrame = v.extract()?;
                Some(df.into())
            }
            None => None,
        };
        Ok(())
    }

    #[getter]
    pub fn performance(&self) -> Option<PerformanceMetrics> {
        self.performance.clone()
    }
}
