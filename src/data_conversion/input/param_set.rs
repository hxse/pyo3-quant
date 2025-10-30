use crate::data_conversion::input::Param;
use pyo3::prelude::*;
use pyo3::Bound;
use std::collections::HashMap;

pub type IndicatorsParams = HashMap<String, Vec<HashMap<String, HashMap<String, Param>>>>;
pub type SignalParams = HashMap<String, Param>;

#[derive(Debug, Clone, Copy, Eq, PartialEq, Hash)]
pub enum PerformanceMetric {
    TotalReturn,
    SharpeRatio,
    MaxDrawdown,
}

impl PerformanceMetric {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::TotalReturn => "total_return",
            Self::SharpeRatio => "sharpe_ratio",
            Self::MaxDrawdown => "max_drawdown",
        }
    }
}

impl<'source> FromPyObject<'source> for PerformanceMetric {
    fn extract_bound(ob: &Bound<'source, PyAny>) -> PyResult<Self> {
        let s: String = ob.extract()?;
        match s.as_str() {
            "total_return" => Ok(Self::TotalReturn),
            "sharpe_ratio" => Ok(Self::SharpeRatio),
            "max_drawdown" => Ok(Self::MaxDrawdown),
            _ => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Unknown metric: {}",
                s
            ))),
        }
    }
}

#[derive(Clone, Debug, FromPyObject)]
pub struct BacktestParams {
    pub sl: Param,
    pub tp: Param,
    pub position_pct: Param,
}

#[derive(Debug, Clone, FromPyObject)]
pub struct PerformanceParams {
    pub metrics: Vec<PerformanceMetric>,
}

#[derive(Debug, Clone, FromPyObject)]
pub struct SingleParam {
    pub indicators: IndicatorsParams,
    pub signal: SignalParams,
    pub backtest: BacktestParams,
    pub performance: PerformanceParams,
}

pub type ParamContainer = Vec<SingleParam>;
