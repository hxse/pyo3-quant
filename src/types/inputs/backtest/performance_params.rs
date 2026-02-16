use super::PerformanceMetric;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;

#[gen_stub_pyclass]
#[pyclass(get_all, set_all)]
#[derive(Debug, Clone, Default)]
pub struct PerformanceParams {
    pub metrics: Vec<PerformanceMetric>,
    pub risk_free_rate: f64,
    pub leverage_safety_factor: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl PerformanceParams {
    #[new]
    #[pyo3(signature = (*, metrics=None, risk_free_rate=0.0, leverage_safety_factor=None))]
    pub fn new(
        metrics: Option<Vec<PerformanceMetric>>,
        risk_free_rate: f64,
        leverage_safety_factor: Option<f64>,
    ) -> Self {
        Self {
            metrics: metrics.unwrap_or_default(),
            risk_free_rate,
            leverage_safety_factor,
        }
    }

    /// 业务层设置绩效指标列表。
    pub fn apply_metrics(&mut self, metrics: Vec<PerformanceMetric>) {
        self.metrics = metrics;
    }

    /// 业务层设置无风险利率。
    pub fn apply_risk_free_rate(&mut self, value: f64) {
        self.risk_free_rate = value;
    }

    /// 业务层设置杠杆安全系数。
    pub fn apply_leverage_safety_factor(&mut self, value: Option<f64>) {
        self.leverage_safety_factor = value;
    }
}
