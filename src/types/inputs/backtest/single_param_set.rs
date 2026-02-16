use super::{BacktestParams, IndicatorsParams, PerformanceMetric, PerformanceParams, SignalParams};
use crate::types::Param;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;

#[gen_stub_pyclass]
#[pyclass(get_all, set_all)]
#[derive(Debug, Clone, Default)]
pub struct SingleParamSet {
    pub indicators: IndicatorsParams,
    pub signal: SignalParams,
    pub backtest: BacktestParams,
    pub performance: PerformanceParams,
}

#[gen_stub_pymethods]
#[pymethods]
impl SingleParamSet {
    #[new]
    #[pyo3(signature = (*, indicators=None, signal=None, backtest=None, performance=None))]
    pub fn new(
        indicators: Option<IndicatorsParams>,
        signal: Option<SignalParams>,
        backtest: Option<BacktestParams>,
        performance: Option<PerformanceParams>,
    ) -> Self {
        Self {
            indicators: indicators.unwrap_or_default(),
            signal: signal.unwrap_or_default(),
            backtest: backtest.unwrap_or_default(),
            performance: performance.unwrap_or_default(),
        }
    }

    /// 业务层一次性替换指标参数容器。
    pub fn set_indicators_params(&mut self, indicators: IndicatorsParams) {
        self.indicators = indicators;
    }

    /// 业务层一次性替换信号参数容器。
    pub fn set_signal_params(&mut self, signal: SignalParams) {
        self.signal = signal;
    }

    /// 业务层一次性替换回测参数容器。
    pub fn set_backtest_params(&mut self, backtest: BacktestParams) {
        self.backtest = backtest;
    }

    /// 业务层一次性替换绩效参数容器。
    pub fn set_performance_params(&mut self, performance: PerformanceParams) {
        self.performance = performance;
    }

    /// 业务层设置单个指标参数，按 data_key/indicator/param_name 精确落位。
    pub fn set_indicator_param(
        &mut self,
        data_key: String,
        indicator_name: String,
        param_name: String,
        param: Param,
    ) {
        self.indicators
            .entry(data_key)
            .or_default()
            .entry(indicator_name)
            .or_default()
            .insert(param_name, param);
    }

    /// 业务层设置单个信号参数。
    pub fn set_signal_param(&mut self, name: String, param: Param) {
        self.signal.insert(name, param);
    }

    /// 业务层设置回测可优化参数（Option<Param> 字段）。
    pub fn set_backtest_optimizable_param(
        &mut self,
        name: &str,
        value: Option<Param>,
    ) -> PyResult<()> {
        self.backtest.set_optimizable_param(name, value)
    }

    /// 业务层设置回测布尔参数。
    pub fn set_backtest_bool_param(&mut self, name: &str, value: bool) -> PyResult<()> {
        self.backtest.set_bool_param(name, value)
    }

    /// 业务层设置回测数值参数。
    pub fn set_backtest_f64_param(&mut self, name: &str, value: f64) -> PyResult<()> {
        self.backtest.set_f64_param(name, value)
    }

    /// 业务层设置绩效指标列表。
    pub fn set_performance_metrics(&mut self, metrics: Vec<PerformanceMetric>) {
        self.performance.apply_metrics(metrics);
    }

    /// 业务层设置绩效无风险利率。
    pub fn set_performance_risk_free_rate(&mut self, value: f64) {
        self.performance.apply_risk_free_rate(value);
    }

    /// 业务层设置杠杆安全系数。
    pub fn set_performance_leverage_safety_factor(&mut self, value: Option<f64>) {
        self.performance.apply_leverage_safety_factor(value);
    }
}

pub type ParamContainer = Vec<SingleParamSet>;
