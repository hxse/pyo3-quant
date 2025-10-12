use polars::prelude::*;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use pyo3_polars::PyDataFrame;
use std::collections::HashMap;

// 替换原来的 struct 定义
pub type PerformanceMetrics = HashMap<String, f64>;

#[derive(Debug)]
pub struct BacktestSummary {
    pub performance: Option<PerformanceMetrics>,
    pub indicators: Option<Vec<PyDataFrame>>, // 从 Option<PyDataFrame> 改为 Vec
    pub signals: Option<PyDataFrame>,
    pub backtest: Option<PyDataFrame>,
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

        // 设置 indicators 字段，处理 Option<Vec<PyDataFrame>>
        match self.indicators {
            Some(dfs) => {
                let py_list = pyo3::types::PyList::empty(py);
                for df in dfs {
                    py_list.append(df)?;
                }
                dict.set_item("indicators", py_list)?;
            }
            None => dict.set_item("indicators", py.None())?,
        }

        // 设置 signals 字段，处理 Option<PyDataFrame>
        match self.signals {
            Some(df) => dict.set_item("signals", df)?,
            None => dict.set_item("signals", py.None())?,
        }

        // 设置 backtest_result 字段，处理 Option<PyDataFrame>
        match self.backtest {
            Some(df) => dict.set_item("backtest_result", df)?,
            None => dict.set_item("backtest_result", py.None())?,
        }

        Ok(dict)
    }
}
