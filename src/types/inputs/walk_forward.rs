use crate::types::OptimizerConfig;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use pyo3_stub_gen::PyStubType;

/// WF 预热模式（Rust 单一事实源）。
#[pyclass(eq, eq_int, hash, frozen)]
#[derive(Debug, Clone, Copy, Eq, PartialEq, Hash)]
pub enum WfWarmupMode {
    BorrowFromTrain,
    ExtendTest,
    NoWarmup,
}

#[gen_stub_pymethods]
#[pymethods]
impl WfWarmupMode {
    /// 返回枚举变体名（用于展示/日志）。
    pub fn name(&self) -> &'static str {
        match self {
            Self::BorrowFromTrain => "BorrowFromTrain",
            Self::ExtendTest => "ExtendTest",
            Self::NoWarmup => "NoWarmup",
        }
    }

    /// 返回稳定业务键名（用于程序逻辑）。
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::BorrowFromTrain => "borrow_from_train",
            Self::ExtendTest => "extend_test",
            Self::NoWarmup => "no_warmup",
        }
    }

    fn __str__(&self) -> String {
        self.name().to_string()
    }

    fn __repr__(&self) -> String {
        format!("WfWarmupMode.{}", self.name())
    }
}

impl PyStubType for WfWarmupMode {
    fn type_output() -> pyo3_stub_gen::TypeInfo {
        pyo3_stub_gen::TypeInfo::locally_defined("WfWarmupMode", pyo3_stub_gen::ModuleRef::Default)
    }
}

pyo3_stub_gen::inventory::submit! {
    pyo3_stub_gen::type_info::PyEnumInfo {
        enum_id: || std::any::TypeId::of::<WfWarmupMode>(),
        pyclass_name: "WfWarmupMode",
        module: Some("pyo3_quant._pyo3_quant"),
        doc: "WF 预热模式枚举",
        variants: &[
            ("BorrowFromTrain", "借训练尾部作为过渡预热"),
            ("ExtendTest", "训练后扩展过渡区再进入测试"),
            ("NoWarmup", "关闭指标预热补全，仅保留最小过渡锚点"),
        ],
    }
}

/// 向前滚动优化配置
#[gen_stub_pyclass]
#[pyclass(get_all, set_all)]
#[derive(Debug, Clone)]
pub struct WalkForwardConfig {
    /// 训练窗口长度（固定 bar 数）
    pub train_bars: usize,
    /// 过渡窗口长度（固定 bar 数）
    pub transition_bars: usize,
    /// 测试窗口长度（固定 bar 数）
    pub test_bars: usize,
    /// WF 预热模式（BorrowFromTrain / ExtendTest / NoWarmup）
    pub wf_warmup_mode: WfWarmupMode,
    /// 是否从上一窗口继承权重先验，默认 true
    pub inherit_prior: bool,
    /// 内嵌的单次优化器配置
    pub optimizer_config: OptimizerConfig,
}

#[gen_stub_pymethods]
#[pymethods]
impl WalkForwardConfig {
    #[new]
    #[pyo3(signature = (*, train_bars, transition_bars, test_bars, wf_warmup_mode=self::WfWarmupMode::ExtendTest, inherit_prior=true, optimizer_config=None))]
    pub fn new(
        train_bars: usize,
        transition_bars: usize,
        test_bars: usize,
        wf_warmup_mode: WfWarmupMode,
        inherit_prior: bool,
        optimizer_config: Option<OptimizerConfig>,
    ) -> Self {
        Self {
            train_bars,
            transition_bars,
            test_bars,
            wf_warmup_mode,
            inherit_prior,
            optimizer_config: optimizer_config.unwrap_or_default(),
        }
    }
}

impl Default for WalkForwardConfig {
    fn default() -> Self {
        // 中文注释：默认使用固定 bar 口径，避免随总样本增长导致窗口漂移。
        Self::new(500, 100, 200, WfWarmupMode::ExtendTest, true, None)
    }
}
