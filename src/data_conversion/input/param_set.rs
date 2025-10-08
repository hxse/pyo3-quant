use crate::data_conversion::input::Param;
use pyo3::exceptions::PyKeyError;
use pyo3::prelude::*;
use pyo3::types::PyDict;
use pyo3::Bound;
use std::collections::HashMap;

pub type IndicatorsParams = Vec<HashMap<String, HashMap<String, Param>>>;
pub type SignalParams = HashMap<String, Param>;
pub type RiskParams = HashMap<String, Param>;

#[derive(Clone, Debug, FromPyObject)]
pub struct BacktestParams {
    pub sl: Param,
    pub tp: Param,
    pub position_pct: Param,
}

#[derive(Debug, Clone, FromPyObject)]
pub struct PerformanceParams {
    pub metrics: Vec<String>,
}

/// Indicator 配置的包装类型
#[derive(Clone, Debug)] // 移除 FromPyObject，因为它已经手动实现
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

#[derive(Debug, Clone, FromPyObject)] // 移除 #[pyclass]
pub struct ProcessedSingleParam {
    pub indicators: IndicatorsParams,
    pub signal: SignalParams,
    pub backtest: BacktestParams,
    pub risk: RiskParams,
    pub performance: PerformanceParams,
}

#[derive(Debug, Clone, FromPyObject)] // 移除 #[pyclass]
pub struct ProcessedParamSet {
    pub params: Vec<ProcessedSingleParam>,
}
