use pyo3::{exceptions::PyKeyError, prelude::*};

#[derive(Debug, Clone)]
pub enum LogicOp {
    AND,
    OR,
}

impl<'py> FromPyObject<'py> for LogicOp {
    fn extract_bound(ob: &Bound<'py, PyAny>) -> PyResult<Self> {
        let s: String = ob.extract()?;
        match s.as_str() {
            "and" => Ok(LogicOp::AND),
            "or" => Ok(LogicOp::OR),
            _ => Err(PyErr::new::<PyKeyError, _>(format!(
                "Invalid LogicOp: {}",
                s
            ))),
        }
    }
}

#[derive(Debug, Clone, FromPyObject)]
pub struct SignalGroup {
    pub logic: LogicOp,
    /// 条件字符串列表，每个字符串会被 nom 解析器转换成 SignalCondition
    /// 语法：`[!] LeftOperand Op RightOperand`
    /// 示例：`"close, ohlcv_15m, 0 > sma_0, ohlcv_15m, 0"` 或 `"rsi_0, ohlcv_1h, 0 < $rsi_lower"`
    pub comparisons: Vec<String>,
    pub sub_groups: Vec<SignalGroup>,
}

#[derive(Debug, Clone, FromPyObject)]
pub struct SignalTemplate {
    pub name: String,
    pub enter_long: Option<SignalGroup>,
    pub exit_long: Option<SignalGroup>,
    pub enter_short: Option<SignalGroup>,
    pub exit_short: Option<SignalGroup>,
}

#[derive(Debug, Clone, FromPyObject)] // 添加 FromPyObject
pub struct TemplateContainer {
    pub signal: SignalTemplate,
}
