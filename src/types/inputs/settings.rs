use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use pyo3_stub_gen::PyStubType;

// 定义执行阶段枚举，派生 PartialOrd、Ord 以支持阶段比较
#[pyclass(eq, eq_int, hash, frozen)]
#[derive(Debug, Clone, Copy, Eq, PartialEq, Hash, PartialOrd, Ord)]
pub enum ExecutionStage {
    Idle,
    Indicator,
    Signals,
    Backtest,
    Performance,
}

#[gen_stub_pymethods]
#[pymethods]
impl ExecutionStage {
    /// 返回枚举变体名（用于展示/日志）
    pub fn name(&self) -> &'static str {
        match self {
            Self::Idle => "Idle",
            Self::Indicator => "Indicator",
            Self::Signals => "Signals",
            Self::Backtest => "Backtest",
            Self::Performance => "Performance",
        }
    }

    /// 返回稳定的业务键名（用于程序逻辑）
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Idle => "idle",
            Self::Indicator => "indicator",
            Self::Signals => "signals",
            Self::Backtest => "backtest",
            Self::Performance => "performance",
        }
    }

    fn __str__(&self) -> String {
        self.name().to_string()
    }

    fn __repr__(&self) -> String {
        format!("ExecutionStage.{}", self.name())
    }
}

impl PyStubType for ExecutionStage {
    fn type_output() -> pyo3_stub_gen::TypeInfo {
        pyo3_stub_gen::TypeInfo::locally_defined(
            "ExecutionStage",
            pyo3_stub_gen::ModuleRef::Default,
        )
    }
}

pyo3_stub_gen::inventory::submit! {
    pyo3_stub_gen::type_info::PyEnumInfo {
        enum_id: || std::any::TypeId::of::<ExecutionStage>(),
        pyclass_name: "ExecutionStage",
        module: Some("pyo3_quant._pyo3_quant"),
        doc: "执行阶段指标枚举",
        variants: &[
            ("Idle", "空闲/未开始"),
            ("Indicator", "指标计算"),
            ("Signals", "信号生成"),
            ("Backtest", "回测执行"),
            ("Performance", "性能评估"),
        ],
    }
}

#[gen_stub_pyclass]
#[pyclass(get_all, set_all)]
#[derive(Debug, Clone)]
pub struct SettingContainer {
    pub execution_stage: ExecutionStage,
    pub return_only_final: bool,
}

#[gen_stub_pymethods]
#[pymethods]
impl SettingContainer {
    #[new]
    #[pyo3(signature = (*, execution_stage=self::ExecutionStage::Performance, return_only_final=false))]
    pub fn new(execution_stage: ExecutionStage, return_only_final: bool) -> Self {
        Self {
            execution_stage,
            return_only_final,
        }
    }
}

impl Default for SettingContainer {
    fn default() -> Self {
        Self::new(self::ExecutionStage::Performance, false)
    }
}
