use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use std::collections::HashMap;

/// 单个指标实例的预热契约。
#[gen_stub_pyclass]
#[pyclass(get_all, set_all)]
#[derive(Debug, Clone)]
pub struct IndicatorContract {
    pub source: String,
    pub warmup_bars: usize,
    pub warmup_mode: String,
}

#[gen_stub_pymethods]
#[pymethods]
impl IndicatorContract {
    #[new]
    pub fn new(source: String, warmup_bars: usize, warmup_mode: String) -> Self {
        Self {
            source,
            warmup_bars,
            warmup_mode,
        }
    }
}

/// 指标契约聚合结果（PyO3 对外强类型）。
#[gen_stub_pyclass]
#[pyclass(get_all, set_all)]
#[derive(Debug, Clone)]
pub struct IndicatorContractReport {
    pub warmup_bars_by_source: HashMap<String, usize>,
    pub contracts_by_indicator: HashMap<String, IndicatorContract>,
}

#[gen_stub_pymethods]
#[pymethods]
impl IndicatorContractReport {
    #[new]
    pub fn new(
        warmup_bars_by_source: HashMap<String, usize>,
        contracts_by_indicator: HashMap<String, IndicatorContract>,
    ) -> Self {
        Self {
            warmup_bars_by_source,
            contracts_by_indicator,
        }
    }
}
