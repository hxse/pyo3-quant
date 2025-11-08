use pyo3::exceptions::PyKeyError;
use pyo3::prelude::*;

#[derive(Debug, Clone)] // 移除 FromPyObject
pub enum CompareOp {
    GT,  // >
    LT,  // <
    GE,  // >=
    LE,  // <=
    EQ,  // ==
    NE,  // !=
    CGT, // > 交叉
    CLT, // < 交叉
    CGE, // >= 交叉
    CLE, // <= 交叉
    CEQ, // == 交叉
    CNE, // != 交叉
}

impl<'py> FromPyObject<'py> for CompareOp {
    fn extract_bound(ob: &Bound<'py, PyAny>) -> PyResult<Self> {
        let s: String = ob.extract()?;
        match s.as_str() {
            "GT" => Ok(CompareOp::GT),
            "LT" => Ok(CompareOp::LT),
            "GE" => Ok(CompareOp::GE),
            "LE" => Ok(CompareOp::LE),
            "EQ" => Ok(CompareOp::EQ),
            "NE" => Ok(CompareOp::NE),
            "CGT" => Ok(CompareOp::CGT),
            "CLT" => Ok(CompareOp::CLT),
            "CGE" => Ok(CompareOp::CGE),
            "CLE" => Ok(CompareOp::CLE),
            "CEQ" => Ok(CompareOp::CEQ),
            "CNE" => Ok(CompareOp::CNE),
            _ => Err(PyErr::new::<PyKeyError, _>(format!(
                "Invalid CompareOp: {}",
                s
            ))),
        }
    }
}

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
pub struct ParamOperand {
    pub name: String,
}

// Signal 专用：带时间框架
#[derive(Debug, Clone, FromPyObject)]
pub struct SignalDataOperand {
    pub name: String,
    pub source: String,
    pub offset: u32,
}

#[derive(Debug, Clone)]
pub enum SignalRightOperand {
    Data(SignalDataOperand),
    Param(ParamOperand),
}

impl<'py> FromPyObject<'py> for SignalRightOperand {
    fn extract_bound(ob: &Bound<'py, PyAny>) -> PyResult<Self> {
        let tag: String = ob.getattr("_tag")?.extract()?;
        match tag.as_str() {
            "Data" => Ok(SignalRightOperand::Data(ob.extract()?)),
            "Param" => Ok(SignalRightOperand::Param(ob.extract()?)),
            _ => Err(PyErr::new::<PyKeyError, _>(format!(
                "Invalid _tag for SignalRightOperand: {}",
                tag
            ))),
        }
    }
}

#[derive(Debug, Clone, FromPyObject)]
pub struct SignalCondition {
    pub a: SignalDataOperand,
    pub b: SignalRightOperand,
    pub compare: CompareOp,
}

#[derive(Debug, Clone, FromPyObject)]
pub struct SignalGroup {
    pub logic: LogicOp,
    pub conditions: Vec<SignalCondition>,
}

#[derive(Debug, Clone, FromPyObject)]
pub struct SignalTemplate {
    pub name: String,
    pub enter_long: Option<Vec<SignalGroup>>,
    pub exit_long: Option<Vec<SignalGroup>>,
    pub enter_short: Option<Vec<SignalGroup>>,
    pub exit_short: Option<Vec<SignalGroup>>,
}

#[derive(Debug, Clone, FromPyObject)] // 添加 FromPyObject
pub struct TemplateContainer {
    pub signal: SignalTemplate,
}
