use polars::prelude::*;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use pyo3_polars::PyDataFrame;
use std::collections::HashMap;

// 替换原来的 struct 定义
pub type PerformanceMetrics = HashMap<String, f64>;
pub type IndicatorResults = HashMap<String, Vec<DataFrame>>;

#[derive(Debug, Clone)]
pub struct BacktestSummary {
    pub indicators: Option<IndicatorResults>,
    pub signals: Option<DataFrame>,
    pub backtest: Option<DataFrame>,
    pub performance: Option<PerformanceMetrics>,
}

impl<'py> IntoPyObject<'py> for BacktestSummary {
    type Target = PyDict;
    type Output = Bound<'py, PyDict>;
    type Error = PyErr;

    fn into_pyobject(self, py: Python<'py>) -> Result<Self::Output, Self::Error> {
        let dict = PyDict::new(py);

        // 设置 performance 字段
        match self.performance {
            Some(perf) => dict.set_item("performance", perf)?,
            None => dict.set_item("performance", py.None())?,
        }

        // 设置 indicators 字段，处理 Option<Vec<DataFrame>>
        match self.indicators {
            Some(indicators_map) => {
                let py_dict = PyDict::new(py);
                for (key, dfs) in indicators_map {
                    let py_list = pyo3::types::PyList::empty(py);
                    for df in dfs {
                        py_list.append(PyDataFrame(df))?;
                    }
                    py_dict.set_item(key, py_list)?;
                }
                dict.set_item("indicators", py_dict)?;
            }
            None => dict.set_item("indicators", py.None())?,
        }

        // 设置 signals 字段，处理 Option<DataFrame>
        match self.signals {
            Some(df) => dict.set_item("signals", PyDataFrame(df))?,
            None => dict.set_item("signals", py.None())?,
        }

        // 设置 backtest_result 字段，处理 Option<DataFrame>
        match self.backtest {
            Some(df) => dict.set_item("backtest_result", PyDataFrame(df))?,
            None => dict.set_item("backtest_result", py.None())?,
        }

        Ok(dict)
    }
}

impl<'source> FromPyObject<'source> for BacktestSummary {
    fn extract_bound(ob: &Bound<'source, PyAny>) -> PyResult<Self> {
        // 从Python对象中提取数据
        let dict = ob.downcast::<PyDict>()?;

        // 提取 performance 字段
        let performance = match dict.get_item("performance")? {
            Some(value) => {
                if value.is_none() {
                    None
                } else {
                    Some(value.extract::<HashMap<String, f64>>()?)
                }
            }
            None => None,
        };

        // 提取 indicators 字段
        let indicators = match dict.get_item("indicators")? {
            Some(value) => {
                if value.is_none() {
                    None
                } else {
                    let ind_dict = value.downcast::<PyDict>()?;
                    let mut indicators_map = HashMap::new();
                    for (key, val) in ind_dict.iter() {
                        let key_str = key.extract::<String>()?;
                        let py_list: Vec<PyDataFrame> = val.extract()?;
                        let dfs: Vec<DataFrame> =
                            py_list.into_iter().map(|py_df| py_df.into()).collect();
                        indicators_map.insert(key_str, dfs);
                    }
                    Some(indicators_map)
                }
            }
            None => None,
        };

        // 提取 signals 字段
        let signals = match dict.get_item("signals")? {
            Some(value) => {
                if value.is_none() {
                    None
                } else {
                    let py_df: PyDataFrame = value.extract()?;
                    Some(py_df.into())
                }
            }
            None => None,
        };

        // 提取 backtest_result 字段
        let backtest = match dict.get_item("backtest_result")? {
            Some(value) => {
                if value.is_none() {
                    None
                } else {
                    let py_df: PyDataFrame = value.extract()?;
                    Some(py_df.into())
                }
            }
            None => None,
        };

        Ok(BacktestSummary {
            indicators,
            signals,
            backtest,
            performance,
        })
    }
}
