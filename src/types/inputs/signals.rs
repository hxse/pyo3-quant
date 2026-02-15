use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use pyo3_stub_gen::PyStubType;

#[pyclass(eq, eq_int, hash, frozen)]
#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum LogicOp {
    AND,
    OR,
}

impl PyStubType for LogicOp {
    fn type_output() -> pyo3_stub_gen::TypeInfo {
        pyo3_stub_gen::TypeInfo::locally_defined("LogicOp", pyo3_stub_gen::ModuleRef::Default)
    }
}

pyo3_stub_gen::inventory::submit! {
    pyo3_stub_gen::type_info::PyEnumInfo {
        enum_id: || std::any::TypeId::of::<LogicOp>(),
        pyclass_name: "LogicOp",
        module: Some("pyo3_quant._pyo3_quant"),
        doc: "逻辑操作枚举",
        variants: &[
            ("AND", "逻辑与"),
            ("OR", "逻辑或"),
        ],
    }
}

#[gen_stub_pyclass]
#[pyclass(get_all, set_all)]
#[derive(Debug, Clone)]
pub struct SignalGroup {
    pub logic: LogicOp,
    /// 条件字符串列表，每个字符串会被 nom 解析器转换成 SignalCondition
    /// 语法：`[!] LeftOperand Op RightOperand`
    /// 示例：`"close, ohlcv_15m, 0 > sma_0, ohlcv_15m, 0"` 或 `"rsi_0, ohlcv_1h, 0 < $rsi_lower"`
    pub comparisons: Vec<String>,
    pub sub_groups: Vec<SignalGroup>,
}

#[gen_stub_pymethods]
#[pymethods]
impl SignalGroup {
    #[new]
    #[pyo3(signature = (*, logic, comparisons=None, sub_groups=None))]
    pub fn new(
        logic: LogicOp,
        comparisons: Option<Vec<String>>,
        sub_groups: Option<Vec<SignalGroup>>,
    ) -> Self {
        Self {
            logic,
            comparisons: comparisons.unwrap_or_default(),
            sub_groups: sub_groups.unwrap_or_default(),
        }
    }
}

#[gen_stub_pyclass]
#[pyclass(get_all, set_all)]
#[derive(Debug, Clone, Default)]
pub struct SignalTemplate {
    pub entry_long: Option<SignalGroup>,
    pub exit_long: Option<SignalGroup>,
    pub entry_short: Option<SignalGroup>,
    pub exit_short: Option<SignalGroup>,
}

#[gen_stub_pymethods]
#[pymethods]
impl SignalTemplate {
    #[new]
    #[pyo3(signature = (*, entry_long=None, exit_long=None, entry_short=None, exit_short=None))]
    pub fn new(
        entry_long: Option<SignalGroup>,
        exit_long: Option<SignalGroup>,
        entry_short: Option<SignalGroup>,
        exit_short: Option<SignalGroup>,
    ) -> Self {
        Self {
            entry_long,
            exit_long,
            entry_short,
            exit_short,
        }
    }
}

#[gen_stub_pyclass]
#[pyclass(get_all, set_all)]
#[derive(Debug, Clone)]
pub struct TemplateContainer {
    pub signal: SignalTemplate,
}

#[gen_stub_pymethods]
#[pymethods]
impl TemplateContainer {
    #[new]
    pub fn new(signal: SignalTemplate) -> Self {
        Self { signal }
    }
}
