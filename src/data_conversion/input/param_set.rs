use pyo3::prelude::*;
use pyo3::types::PyDict;
use pyo3::Bound;
use pyo3::exceptions::PyKeyError;
use std::collections::HashMap;
use crate::data_conversion::input::Param;

pub type IndicatorsParams = Vec<HashMap<String, HashMap<String, Param>>>;
pub type SignalParams = HashMap<String, Param>;
pub type RiskParams = HashMap<String, Param>;


#[derive(Clone, Debug, FromPyObject)]
#[pyo3(from_item_all)]
pub struct BacktestParams {
    pub sl: Param,
    pub tp: Param,
    pub position_pct: Param,
}

#[derive(Debug, Clone, FromPyObject)]
#[pyo3(from_item_all)]
pub struct PerformanceParams {
    pub metrics: Vec<String>,
}

/// Indicator 配置的包装类型
#[derive(Clone, Debug)]
pub struct IndicatorConfig(pub Vec<HashMap<String, HashMap<String, Param>>>);

// 为 IndicatorConfig 实现 FromPyObject
impl<'py> FromPyObject<'py> for IndicatorConfig {
    fn extract_bound(ob: &Bound<'py, PyAny>) -> PyResult<Self> {
        // 确保是列表类型
        let list = ob.downcast::<pyo3::types::PyList>()?;

        let mut result = Vec::new();

        // 遍历列表中的每个字典
        for item in list.iter() {
            let indicator_dict = item.downcast::<PyDict>()?;

            // 直接使用 extract 提取整个嵌套结构
            // PyO3 会递归处理 HashMap<String, HashMap<String, Param>>
            let processed_map: HashMap<String, HashMap<String, Param>> =
                indicator_dict.extract()?;

            result.push(processed_map);
        }

        Ok(IndicatorConfig(result))
    }
}


pub struct ProcessedSingleParam {
    pub indicators: IndicatorsParams,
    pub signal: SignalParams,
    pub backtest: BacktestParams,
    pub risk: RiskParams,
    pub performance: PerformanceParams,
}

pub struct ProcessedParamSet {
    pub params: Vec<ProcessedSingleParam>,
}

pub fn parse(
    param_set: Vec<Bound<'_, PyDict>>
) -> PyResult<ProcessedParamSet> {
    let mut params = Vec::new();
    for param_dict_py in param_set {
        let indicator_input_any = param_dict_py
            .get_item("indicator")?
            .ok_or_else(|| PyErr::new::<PyKeyError, _>("Missing 'indicator' key"))?;
        let indicators = indicator_input_any.extract::<IndicatorConfig>()?.0;

        // backtest
        let backtest_input_any = param_dict_py
            .get_item("backtest")?
            .ok_or_else(|| PyErr::new::<PyKeyError, _>("Missing 'backtest' key"))?;
        let backtest = backtest_input_any.extract::<BacktestParams>()?;

        // signal
        let signal_input_any = param_dict_py
            .get_item("signal")?
            .ok_or_else(|| PyErr::new::<PyKeyError, _>("Missing 'signal' key"))?;
        let signal = signal_input_any.extract::<SignalParams>()?;

        // risk
        let risk_input_any = param_dict_py
            .get_item("risk")?
            .ok_or_else(|| PyErr::new::<PyKeyError, _>("Missing 'risk' key"))?;
        let risk = risk_input_any.extract::<RiskParams>()?;

        // performance
        let performance_input_any = param_dict_py
            .get_item("performance")?
            .ok_or_else(|| PyErr::new::<PyKeyError, _>("Missing 'performance' key"))?;
        let performance = performance_input_any.extract::<PerformanceParams>()?;

        params.push(ProcessedSingleParam {
            indicators,
            backtest,
            signal,
            risk,
            performance,  // 添加这一行
        });
    }

    Ok(ProcessedParamSet { params })
}
