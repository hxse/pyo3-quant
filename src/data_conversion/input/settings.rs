use pyo3::prelude::*;
use pyo3::types::PyDict;
use pyo3::{Bound, FromPyObject};

// 定义执行阶段枚举，派生 PartialOrd、Ord 以支持阶段比较
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord)]
pub enum ExecutionStage {
    Indicator,
    Signals,
    Backtest,
    Performance,
}

// 从 Python 枚举转换：接收字符串值并转换
impl<'py> FromPyObject<'py> for ExecutionStage {
    fn extract_bound(ob: &Bound<'py, PyAny>) -> PyResult<Self> {
        let py_str: String = ob.extract()?;
        match py_str.as_str() {
            "indicator" => Ok(ExecutionStage::Indicator),
            "signals" => Ok(ExecutionStage::Signals),
            "backtest" => Ok(ExecutionStage::Backtest),
            "performance" => Ok(ExecutionStage::Performance),
            other => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Invalid execution stage: {}",
                other
            ))),
        }
    }
}

#[derive(Debug, Clone, FromPyObject)]
pub struct ProcessedSettings {
    pub execution_stage: ExecutionStage,
    pub return_only_final: bool,
    pub skip_risk: bool,
}

impl Default for ProcessedSettings {
    fn default() -> Self {
        Self {
            execution_stage: ExecutionStage::Performance,
            return_only_final: false,
            skip_risk: false,
        }
    }
}

pub fn parse(settings: Bound<'_, PyDict>) -> PyResult<ProcessedSettings> {
    settings
        .extract()
        .or_else(|_| Ok(ProcessedSettings::default()))
}
