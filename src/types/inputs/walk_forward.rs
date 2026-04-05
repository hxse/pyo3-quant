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
}

impl WfWarmupMode {
    fn variant_name(&self) -> &'static str {
        match self {
            Self::BorrowFromTrain => "BorrowFromTrain",
            Self::ExtendTest => "ExtendTest",
        }
    }
}

#[gen_stub_pymethods]
#[pymethods]
impl WfWarmupMode {
    /// 返回稳定业务键名（用于程序逻辑）。
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::BorrowFromTrain => "borrow_from_train",
            Self::ExtendTest => "extend_test",
        }
    }

    fn __str__(&self) -> String {
        self.variant_name().to_string()
    }

    fn __repr__(&self) -> String {
        format!("WfWarmupMode.{}", self.variant_name())
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
        ],
    }
}

/// 向前滚动优化配置
#[gen_stub_pyclass]
#[pyclass(get_all, set_all)]
#[derive(Debug, Clone)]
pub struct WalkForwardConfig {
    /// 训练 active 区间长度（固定 bar 数）
    pub train_active_bars: usize,
    /// 测试 active 区间长度（固定 bar 数）
    pub test_active_bars: usize,
    /// 训练包和测试包至少保留多少 base 预热 bar
    pub min_warmup_bars: usize,
    /// WF 预热模式（BorrowFromTrain / ExtendTest）
    pub warmup_mode: WfWarmupMode,
    /// 是否忽略指标预热，只保留 WF 几何与 backtest 执行预热
    pub ignore_indicator_warmup: bool,
    /// 内嵌的单次优化器配置
    pub optimizer_config: OptimizerConfig,
}

#[gen_stub_pymethods]
#[pymethods]
impl WalkForwardConfig {
    #[new]
    #[pyo3(signature = (*, train_active_bars, test_active_bars, min_warmup_bars=0, warmup_mode=self::WfWarmupMode::ExtendTest, ignore_indicator_warmup=false, optimizer_config=None))]
    pub fn new(
        train_active_bars: usize,
        test_active_bars: usize,
        min_warmup_bars: usize,
        warmup_mode: WfWarmupMode,
        ignore_indicator_warmup: bool,
        optimizer_config: Option<OptimizerConfig>,
    ) -> Self {
        Self {
            train_active_bars,
            test_active_bars,
            min_warmup_bars,
            warmup_mode,
            ignore_indicator_warmup,
            optimizer_config: optimizer_config.unwrap_or_default(),
        }
    }
}

impl Default for WalkForwardConfig {
    fn default() -> Self {
        // 中文注释：默认使用固定 active bar 口径，避免随总样本增长导致窗口漂移。
        Self::new(500, 200, 0, WfWarmupMode::ExtendTest, false, None)
    }
}
