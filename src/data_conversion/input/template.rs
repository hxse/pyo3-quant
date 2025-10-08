use pyo3::exceptions::PyKeyError;
use pyo3::prelude::*;
use pyo3::types::PyDict;

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
    pub source: String,
}

// Signal 专用：带时间框架
#[derive(Debug, Clone, FromPyObject)]
pub struct SignalDataOperand {
    pub source: String,
    pub offset: i32,
    pub mtf: i32,
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
    pub target: String,
    pub conditions: Vec<SignalCondition>,
}

#[derive(Debug, Clone, FromPyObject)]
pub struct SignalTemplate {
    pub name: String,
    pub template: Vec<SignalGroup>,
}

// Risk 专用：只有数据源
#[derive(Debug, Clone, FromPyObject)]
pub struct RiskDataOperand {
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
pub struct RiskRule {
    pub logic: String,
    pub target: String,
    pub conditions: Vec<RiskCondition>,
}

#[derive(Debug, Clone, FromPyObject)]
pub struct RiskTemplate {
    pub name: String,
    pub template: Vec<RiskRule>,
}

#[derive(Debug, Clone, FromPyObject)] // 添加 FromPyObject
pub struct ProcessedTemplate {
    pub signal: SignalTemplate,
    pub risk: RiskTemplate,
}
