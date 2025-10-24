use pyo3::exceptions::PyKeyError;
use pyo3::prelude::*;

#[derive(Debug, Clone)] // 移除 FromPyObject
pub enum CompareOp {
    GT,  // "GT" >
    LT,  // "LT" <
    CGT, // "CGT" 向上穿越
    CLT, // "CLT" 向下穿越
    GE,  // "GE" >=
    LE,  // "LE" <=
    EQ,  // "EQ" ==
    NE,  // "NE" !=
}

impl<'py> FromPyObject<'py> for CompareOp {
    fn extract_bound(ob: &Bound<'py, PyAny>) -> PyResult<Self> {
        let s: String = ob.extract()?;
        match s.as_str() {
            "GT" => Ok(CompareOp::GT),
            "LT" => Ok(CompareOp::LT),
            "CGT" => Ok(CompareOp::CGT),
            "CLT" => Ok(CompareOp::CLT),
            "GE" => Ok(CompareOp::GE),
            "LE" => Ok(CompareOp::LE),
            "EQ" => Ok(CompareOp::EQ),
            "NE" => Ok(CompareOp::NE),
            _ => Err(PyErr::new::<PyKeyError, _>(format!(
                "Invalid CompareOp: {}",
                s
            ))),
        }
    }
}

#[derive(Debug, Clone, FromPyObject)]
pub struct ParamOperand {
    pub name: String,
}

// Signal 专用：带时间框架
#[derive(Debug, Clone, FromPyObject)]
pub struct SignalDataOperand {
    pub name: String,
    pub source: String,
    pub source_idx: i32,
    pub offset: i32,
}

// Signal 专用条件
#[derive(Debug, Clone, FromPyObject)]
pub struct SignalCondition {
    pub a_data: Option<SignalDataOperand>,
    pub a_param: Option<ParamOperand>,
    pub b_data: Option<SignalDataOperand>,
    pub b_param: Option<ParamOperand>,
    pub compare: CompareOp,
}

#[derive(Debug, Clone, FromPyObject)]
pub struct SignalGroup {
    pub logic: String,
    pub conditions: Vec<SignalCondition>,
}

#[derive(Debug, Clone, FromPyObject)]
pub struct SignalTemplate {
    pub name: String,
    pub enter_long: Option<SignalGroup>,
    pub exit_long: Option<SignalGroup>,
    pub enter_short: Option<SignalGroup>,
    pub exit_short: Option<SignalGroup>,
}

// Risk 专用：只有数据源
#[derive(Debug, Clone, FromPyObject)]
pub struct RiskDataOperand {
    pub name: String,
    pub source: String,
}

// Risk 专用条件
#[derive(Debug, Clone, FromPyObject)]
pub struct RiskCondition {
    pub a_data: Option<RiskDataOperand>,
    pub a_param: Option<ParamOperand>,
    pub b_data: Option<RiskDataOperand>,
    pub b_param: Option<ParamOperand>,
    pub compare: CompareOp,
}

#[derive(Debug, Clone, FromPyObject)]
pub struct RiskGroup {
    pub logic: String,
    pub conditions: Vec<RiskCondition>,
}

#[derive(Debug, Clone, FromPyObject)]
pub struct RiskTemplate {
    pub name: String,
    pub size_neutral_pct: Option<RiskGroup>,
    pub size_up_pct: Option<RiskGroup>,
    pub size_down_pct: Option<RiskGroup>,
    pub size_skip_pct: Option<RiskGroup>,
}

#[derive(Debug, Clone, FromPyObject)] // 添加 FromPyObject
pub struct TemplateContainer {
    pub signal: SignalTemplate,
    pub risk: RiskTemplate,
}
