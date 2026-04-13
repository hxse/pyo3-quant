use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use pyo3_stub_gen::PyStubType;

// 定义执行阶段枚举，派生 PartialOrd、Ord 以支持阶段比较
#[pyclass(eq, eq_int, hash, frozen)]
#[derive(Debug, Clone, Copy, Eq, PartialEq, Hash, PartialOrd, Ord)]
pub enum ExecutionStage {
    Indicator,
    Signals,
    Backtest,
    Performance,
}

impl ExecutionStage {
    fn variant_name(&self) -> &'static str {
        match self {
            Self::Indicator => "Indicator",
            Self::Signals => "Signals",
            Self::Backtest => "Backtest",
            Self::Performance => "Performance",
        }
    }
}

#[gen_stub_pymethods]
#[pymethods]
impl ExecutionStage {
    /// 返回稳定的业务键名（用于程序逻辑）
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::Indicator => "indicator",
            Self::Signals => "signals",
            Self::Backtest => "backtest",
            Self::Performance => "performance",
        }
    }

    fn __str__(&self) -> String {
        self.variant_name().to_string()
    }

    fn __repr__(&self) -> String {
        format!("ExecutionStage.{}", self.variant_name())
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
            ("Indicator", "指标计算"),
            ("Signals", "信号生成"),
            ("Backtest", "回测执行"),
            ("Performance", "性能评估"),
        ],
    }
}

#[pyclass(eq, eq_int, hash, frozen)]
#[derive(Debug, Clone, Copy, Eq, PartialEq, Hash)]
pub enum ArtifactRetention {
    AllCompletedStages,
    StopStageOnly,
}

impl ArtifactRetention {
    fn variant_name(&self) -> &'static str {
        match self {
            Self::AllCompletedStages => "AllCompletedStages",
            Self::StopStageOnly => "StopStageOnly",
        }
    }
}

#[gen_stub_pymethods]
#[pymethods]
impl ArtifactRetention {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::AllCompletedStages => "all_completed_stages",
            Self::StopStageOnly => "stop_stage_only",
        }
    }

    fn __str__(&self) -> String {
        self.variant_name().to_string()
    }

    fn __repr__(&self) -> String {
        format!("ArtifactRetention.{}", self.variant_name())
    }
}

impl PyStubType for ArtifactRetention {
    fn type_output() -> pyo3_stub_gen::TypeInfo {
        pyo3_stub_gen::TypeInfo::locally_defined(
            "ArtifactRetention",
            pyo3_stub_gen::ModuleRef::Default,
        )
    }
}

pyo3_stub_gen::inventory::submit! {
    pyo3_stub_gen::type_info::PyEnumInfo {
        enum_id: || std::any::TypeId::of::<ArtifactRetention>(),
        pyclass_name: "ArtifactRetention",
        module: Some("pyo3_quant._pyo3_quant"),
        doc: "公开结果保留策略枚举",
        variants: &[
            ("AllCompletedStages", "保留全部已完成阶段"),
            ("StopStageOnly", "只保留 stop 阶段产物"),
        ],
    }
}

#[gen_stub_pyclass]
#[pyclass(get_all, set_all)]
#[derive(Debug, Clone)]
pub struct SettingContainer {
    pub stop_stage: ExecutionStage,
    pub artifact_retention: ArtifactRetention,
}

#[gen_stub_pymethods]
#[pymethods]
impl SettingContainer {
    #[new]
    #[pyo3(signature = (*, stop_stage=self::ExecutionStage::Performance, artifact_retention=self::ArtifactRetention::AllCompletedStages))]
    pub fn new(stop_stage: ExecutionStage, artifact_retention: ArtifactRetention) -> Self {
        Self {
            stop_stage,
            artifact_retention,
        }
    }
}

impl Default for SettingContainer {
    fn default() -> Self {
        Self::new(
            self::ExecutionStage::Performance,
            self::ArtifactRetention::AllCompletedStages,
        )
    }
}
