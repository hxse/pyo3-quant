use super::params_base::Param;
use crate::error::BacktestError;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;
use pyo3_stub_gen::PyStubType;
use std::collections::HashMap;

pub type IndicatorsParams = HashMap<String, HashMap<String, HashMap<String, Param>>>;
pub type SignalParams = HashMap<String, Param>;

#[pyclass(eq, eq_int, hash, frozen)]
#[derive(Debug, Clone, Copy, Eq, PartialEq, Hash)]
pub enum PerformanceMetric {
    TotalReturn,
    MaxDrawdown,
    MaxDrawdownDuration,
    /// 年化夏普比率
    SharpeRatio,
    /// 年化索提诺比率
    SortinoRatio,
    /// 年化卡尔马比率
    CalmarRatio,
    /// 非年化夏普比率（原始）
    SharpeRatioRaw,
    /// 非年化索提诺比率（原始）
    SortinoRatioRaw,
    /// 非年化卡尔马比率（原始）= 总回报率 / 最大回撤
    CalmarRatioRaw,
    TotalTrades,
    AvgDailyTrades,
    WinRate,
    ProfitLossRatio,
    AvgHoldingDuration,
    AvgEmptyDuration,
    MaxHoldingDuration,
    MaxEmptyDuration,
    MaxSafeLeverage,
    AnnualizationFactor,
    HasLeadingNanCount,
}

impl PerformanceMetric {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::TotalReturn => "total_return",
            Self::MaxDrawdown => "max_drawdown",
            Self::SharpeRatio => "sharpe_ratio",
            Self::SortinoRatio => "sortino_ratio",
            Self::CalmarRatio => "calmar_ratio",
            Self::SharpeRatioRaw => "sharpe_ratio_raw",
            Self::SortinoRatioRaw => "sortino_ratio_raw",
            Self::CalmarRatioRaw => "calmar_ratio_raw",
            Self::MaxDrawdownDuration => "max_drawdown_duration",
            Self::TotalTrades => "total_trades",
            Self::AvgDailyTrades => "avg_daily_trades",
            Self::WinRate => "win_rate",
            Self::ProfitLossRatio => "profit_loss_ratio",
            Self::AvgHoldingDuration => "avg_holding_duration",
            Self::AvgEmptyDuration => "avg_empty_duration",
            Self::MaxHoldingDuration => "max_holding_duration",
            Self::MaxEmptyDuration => "max_empty_duration",
            Self::MaxSafeLeverage => "max_safe_leverage",
            Self::AnnualizationFactor => "annualization_factor",
            Self::HasLeadingNanCount => "has_leading_nan_count",
        }
    }
}

impl PyStubType for PerformanceMetric {
    fn type_output() -> pyo3_stub_gen::TypeInfo {
        pyo3_stub_gen::TypeInfo::locally_defined(
            "PerformanceMetric",
            pyo3_stub_gen::ModuleRef::Default,
        )
    }
}

pyo3_stub_gen::inventory::submit! {
    pyo3_stub_gen::type_info::PyEnumInfo {
        enum_id: || std::any::TypeId::of::<PerformanceMetric>(),
        pyclass_name: "PerformanceMetric",
        module: Some("pyo3_quant._pyo3_quant"),
        doc: "性能指标枚举",
        variants: &[
            ("TotalReturn", "总回报率"),
            ("MaxDrawdown", "最大回撤"),
            ("MaxDrawdownDuration", "最大回撤持续时间"),
            ("SharpeRatio", "年化夏普比率"),
            ("SortinoRatio", "年化索提诺比率"),
            ("CalmarRatio", "年化卡尔马比率"),
            ("SharpeRatioRaw", "非年化夏普比率（原始）"),
            ("SortinoRatioRaw", "非年化索提诺比率（原始）"),
            ("CalmarRatioRaw", "非年化卡尔马比率（原始）"),
            ("TotalTrades", "总交易次数"),
            ("AvgDailyTrades", "平均每日交易次数"),
            ("WinRate", "胜率"),
            ("ProfitLossRatio", "盈亏比"),
            ("AvgHoldingDuration", "平均持仓时间"),
            ("AvgEmptyDuration", "平均空仓时间"),
            ("MaxHoldingDuration", "最大持仓时间"),
            ("MaxEmptyDuration", "最大空仓时间"),
            ("MaxSafeLeverage", "最大安全杠杆"),
            ("AnnualizationFactor", "年化因子"),
            ("HasLeadingNanCount", "前置无效数据计数"),
        ],
    }
}

/// 回测引擎的参数结构体。
/// 包含止损止盈、ATR、资金管理、手续费等所有可配置参数。
/// 参数值为 `Param` 类型，通过 `.value` 访问实际数值。
#[gen_stub_pyclass]
#[pyclass(get_all, set_all)]
#[derive(Clone, Debug)]
pub struct BacktestParams {
    // === 止损止盈参数 (百分比) ===
    /// 百分比止损阈值。当仓位亏损达到此百分比时触发止损。
    /// 如果值 <= 0.0，则不使用百分比止损功能。
    pub sl_pct: Option<Param>,
    /// 百分比止盈阈值。当仓位盈利达到此百分比时触发止盈。
    /// 如果值 <= 0.0，则不使用百分比止盈功能。
    pub tp_pct: Option<Param>,
    /// 百分比跟踪止损阈值。当仓位盈利回撤达到此百分比时触发跟踪止损。
    /// 如果值 <= 0.0，则不使用百分比跟踪止损功能。
    pub tsl_pct: Option<Param>,

    // === ATR止损止盈参数 ===
    /// ATR止损倍数。止损价格基于入场价格减去ATR值乘以该倍数。
    /// 如果值 <= 0.0，则不使用ATR止损功能。
    /// 依赖 `atr_period`，如果 `atr_period` <= 0.0，即使 `sl_atr` > 0.0 也不会启用。
    pub sl_atr: Option<Param>,
    /// ATR止盈倍数。止盈价格基于入场价格加上ATR值乘以该倍数。
    /// 如果值 <= 0.0，则不使用ATR止盈功能。
    /// 依赖 `atr_period`，如果 `atr_period` <= 0.0，即使 `tp_atr` > 0.0 也不会启用。
    pub tp_atr: Option<Param>,
    /// ATR跟踪止损倍数。跟踪止损价格基于最高价减去ATR值乘以该倍数。
    /// 如果值 <= 0.0，则不使用ATR跟踪止损功能。
    /// 依赖 `atr_period`，如果 `atr_period` <= 0.0，即使 `tsl_atr` > 0.0 也不会启用。
    pub tsl_atr: Option<Param>,
    /// ATR计算周期。用于计算平均真实范围 (ATR) 的K线周期数。
    /// 如果值 <= 0.0，则所有ATR相关的止损止盈功能都不会启用。
    pub atr_period: Option<Param>,

    // === PSAR 跟踪止损参数 ===
    /// PSAR 初始加速因子。
    /// 三个参数必须同时存在或同时不存在，存在时都必须大于0。
    pub tsl_psar_af0: Option<Param>,
    /// PSAR 加速因子步进。
    pub tsl_psar_af_step: Option<Param>,
    /// PSAR 最大加速因子。
    pub tsl_psar_max_af: Option<Param>,

    /// ATR跟踪止损更新模式。
    /// `false` (默认) 表示只有在价格突破新高/低时才更新TSL ATR价格。
    /// `true` 表示每根K线都会尝试更新TSL ATR价格。
    /// 无论设置如何，多头TSL只能上移，空头TSL只能下移。
    pub tsl_atr_tight: bool,

    // === 离场方式 ===
    /// sl 离场时机选择。
    /// `true` 表示在当前K线内部触发条件时立即离场。
    /// `false` 表示延迟到下一根K线的开盘价离场。
    pub sl_exit_in_bar: bool,

    /// tp 离场时机选择。
    /// `true` 表示在当前K线内部触发条件时立即离场。
    /// `false` 表示延迟到下一根K线的开盘价离场。
    pub tp_exit_in_bar: bool,

    // === 触发模式 (trigger_mode) ===
    // 控制用什么价格检测止损止盈是否触发
    // `false` = 使用 close 检测
    // `true` = 使用 high/low 检测
    /// SL 触发模式
    pub sl_trigger_mode: bool,
    /// TP 触发模式
    pub tp_trigger_mode: bool,
    /// TSL 触发模式 (含 tsl_atr, tsl_pct, tsl_psar)
    pub tsl_trigger_mode: bool,

    // === 锚点模式 (anchor_mode) ===
    // 控制用什么价格作为计算 SL/TP/TSL 的锚点
    // `false` = 使用 close 作为锚点
    // `true` = 使用 high/low (对于SL/TP) 或 extremum (对于TSL) 作为锚点
    /// SL 锚点模式
    pub sl_anchor_mode: bool,
    /// TP 锚点模式
    pub tp_anchor_mode: bool,
    /// TSL 锚点模式 (仅影响 tsl_atr, tsl_pct，不影响 tsl_psar)
    pub tsl_anchor_mode: bool,

    // === 资金管理 ===
    /// 初始本金。回测开始时的账户资金量 (USD)。
    /// 必须大于 0.0。
    pub initial_capital: f64,
    // === 手续费 ===
    /// 固定手续费。每笔交易的固定手续费金额 (USD)。
    /// 必须 >= 0.0。
    pub fee_fixed: f64,
    /// 百分比手续费。每笔交易金额的百分比手续费。
    /// 必须 >= 0.0。
    pub fee_pct: f64,
}

#[gen_stub_pymethods]
#[pymethods]
impl BacktestParams {
    #[new]
    #[allow(clippy::too_many_arguments)]
    #[pyo3(signature = (
        *,
        sl_pct=None,
        tp_pct=None,
        tsl_pct=None,
        sl_atr=None,
        tp_atr=None,
        tsl_atr=None,
        atr_period=None,
        tsl_psar_af0=None,
        tsl_psar_af_step=None,
        tsl_psar_max_af=None,
        tsl_atr_tight=false,
        sl_exit_in_bar=true,
        tp_exit_in_bar=true,
        sl_trigger_mode=true,
        tp_trigger_mode=true,
        tsl_trigger_mode=true,
        sl_anchor_mode=false,
        tp_anchor_mode=false,
        tsl_anchor_mode=false,
        initial_capital=10000.0,
        fee_fixed=0.0,
        fee_pct=0.0006
    ))]
    pub fn new(
        sl_pct: Option<Param>,
        tp_pct: Option<Param>,
        tsl_pct: Option<Param>,
        sl_atr: Option<Param>,
        tp_atr: Option<Param>,
        tsl_atr: Option<Param>,
        atr_period: Option<Param>,
        tsl_psar_af0: Option<Param>,
        tsl_psar_af_step: Option<Param>,
        tsl_psar_max_af: Option<Param>,
        tsl_atr_tight: bool,
        sl_exit_in_bar: bool,
        tp_exit_in_bar: bool,
        sl_trigger_mode: bool,
        tp_trigger_mode: bool,
        tsl_trigger_mode: bool,
        sl_anchor_mode: bool,
        tp_anchor_mode: bool,
        tsl_anchor_mode: bool,
        initial_capital: f64,
        fee_fixed: f64,
        fee_pct: f64,
    ) -> Self {
        Self {
            initial_capital,
            fee_fixed,
            fee_pct,
            tsl_atr_tight,
            sl_exit_in_bar,
            tp_exit_in_bar,
            sl_trigger_mode,
            tp_trigger_mode,
            tsl_trigger_mode,
            sl_anchor_mode,
            tp_anchor_mode,
            tsl_anchor_mode,
            sl_pct,
            tp_pct,
            tsl_pct,
            sl_atr,
            tp_atr,
            tsl_atr,
            atr_period,
            tsl_psar_af0,
            tsl_psar_af_step,
            tsl_psar_max_af,
            ..Default::default()
        }
    }

    /// 业务层设置可优化参数（Option<Param> 字段）。
    /// 使用字段名精确更新，避免在 Python 侧做深层读改写回。
    pub fn set_optimizable_param(&mut self, name: &str, value: Option<Param>) -> PyResult<()> {
        match name {
            "sl_pct" => self.sl_pct = value,
            "tp_pct" => self.tp_pct = value,
            "tsl_pct" => self.tsl_pct = value,
            "sl_atr" => self.sl_atr = value,
            "tp_atr" => self.tp_atr = value,
            "tsl_atr" => self.tsl_atr = value,
            "atr_period" => self.atr_period = value,
            "tsl_psar_af0" => self.tsl_psar_af0 = value,
            "tsl_psar_af_step" => self.tsl_psar_af_step = value,
            "tsl_psar_max_af" => self.tsl_psar_max_af = value,
            _ => {
                return Err(PyValueError::new_err(format!(
                    "未知的 Backtest 可优化参数: {name}"
                )));
            }
        }
        Ok(())
    }

    /// 业务层设置布尔参数。
    pub fn set_bool_param(&mut self, name: &str, value: bool) -> PyResult<()> {
        match name {
            "tsl_atr_tight" => self.tsl_atr_tight = value,
            "sl_exit_in_bar" => self.sl_exit_in_bar = value,
            "tp_exit_in_bar" => self.tp_exit_in_bar = value,
            "sl_trigger_mode" => self.sl_trigger_mode = value,
            "tp_trigger_mode" => self.tp_trigger_mode = value,
            "tsl_trigger_mode" => self.tsl_trigger_mode = value,
            "sl_anchor_mode" => self.sl_anchor_mode = value,
            "tp_anchor_mode" => self.tp_anchor_mode = value,
            "tsl_anchor_mode" => self.tsl_anchor_mode = value,
            _ => {
                return Err(PyValueError::new_err(format!(
                    "未知的 Backtest 布尔参数: {name}"
                )));
            }
        }
        Ok(())
    }

    /// 业务层设置数值参数。
    pub fn set_f64_param(&mut self, name: &str, value: f64) -> PyResult<()> {
        match name {
            "initial_capital" => self.initial_capital = value,
            "fee_fixed" => self.fee_fixed = value,
            "fee_pct" => self.fee_pct = value,
            _ => {
                return Err(PyValueError::new_err(format!(
                    "未知的 Backtest 数值参数: {name}"
                )));
            }
        }
        Ok(())
    }
}

impl BacktestParams {
    /// 检查sl_pct参数是否有效（不验证其他参数）。
    /// 当 `sl_pct` 存在且其值大于 0.0 时，返回 true。
    pub fn is_sl_pct_param_valid(&self) -> bool {
        self.sl_pct.as_ref().is_some_and(|param| param.value > 0.0)
    }

    /// 检查tp_pct参数是否有效（不验证其他参数）。
    /// 当 `tp_pct` 存在且其值大于 0.0 时，返回 true。
    pub fn is_tp_pct_param_valid(&self) -> bool {
        self.tp_pct.as_ref().is_some_and(|param| param.value > 0.0)
    }

    /// 检查tsl_pct参数是否有效（不验证其他参数）。
    /// 当 `tsl_pct` 存在且其值大于 0.0 时，返回 true。
    pub fn is_tsl_pct_param_valid(&self) -> bool {
        self.tsl_pct.as_ref().is_some_and(|param| param.value > 0.0)
    }

    /// 检查sl_atr参数是否有效（不验证atr_period）。
    /// 当 `sl_atr` 存在且其值大于 0.0 时，返回 true。
    pub fn is_sl_atr_param_valid(&self) -> bool {
        self.sl_atr.as_ref().is_some_and(|param| param.value > 0.0)
    }

    /// 检查tp_atr参数是否有效（不验证atr_period）。
    /// 当 `tp_atr` 存在且其值大于 0.0 时，返回 true。
    pub fn is_tp_atr_param_valid(&self) -> bool {
        self.tp_atr.as_ref().is_some_and(|param| param.value > 0.0)
    }

    /// 检查tsl_atr参数是否有效（不验证atr_period）。
    /// 当 `tsl_atr` 存在且其值大于 0.0 时，返回 true。
    pub fn is_tsl_atr_param_valid(&self) -> bool {
        self.tsl_atr.as_ref().is_some_and(|param| param.value > 0.0)
    }

    /// 检查 PSAR 止损参数是否有效
    /// 三个参数必须全部存在且大于0，或全部不存在
    pub fn is_tsl_psar_param_valid(&self) -> bool {
        self.tsl_psar_af0.as_ref().is_some_and(|p| p.value > 0.0)
            && self
                .tsl_psar_af_step
                .as_ref()
                .is_some_and(|p| p.value > 0.0)
            && self.tsl_psar_max_af.as_ref().is_some_and(|p| p.value > 0.0)
    }

    /// 检查是否有任一ATR参数（sl_atr、tp_atr、tsl_atr）有效。
    pub fn has_any_atr_param(&self) -> bool {
        self.is_sl_atr_param_valid()
            || self.is_tp_atr_param_valid()
            || self.is_tsl_atr_param_valid()
    }

    /// 验证ATR参数的一致性。
    /// 当任一ATR参数有效时，atr_period必须存在且有效。
    /// 如果验证失败，返回错误信息。
    /// 返回 `has_any_atr_param` 的值，表示ATR参数整体是否有效。
    pub fn validate_atr_consistency(&self) -> Result<bool, BacktestError> {
        let has_any_atr_param = self.has_any_atr_param();

        // 只有当存在ATR参数时，才需要验证atr_period
        if has_any_atr_param {
            let atr_period_valid = self
                .atr_period
                .as_ref()
                .is_some_and(|param| param.value > 0.0);

            if !atr_period_valid {
                return Err(BacktestError::InvalidParameter {
                    param_name: "atr_period".to_string(),
                    value: self
                        .atr_period
                        .as_ref()
                        .map(|p| p.value.to_string())
                        .unwrap_or_else(|| "None".to_string()),
                    reason: "当使用任何ATR相关参数时，atr_period必须存在且大于0".to_string(),
                });
            }
        }

        // 如果没有ATR参数，则ATR相关参数视为有效
        // 如果有ATR参数且atr_period有效，则ATR相关参数视为有效
        Ok(has_any_atr_param)
    }

    /// 获取可优化参数的不可变引用
    pub fn get_optimizable_param(&self, name: &str) -> Option<&Param> {
        match name {
            "sl_pct" => self.sl_pct.as_ref(),
            "tp_pct" => self.tp_pct.as_ref(),
            "tsl_pct" => self.tsl_pct.as_ref(),
            "sl_atr" => self.sl_atr.as_ref(),
            "tp_atr" => self.tp_atr.as_ref(),
            "tsl_atr" => self.tsl_atr.as_ref(),
            "atr_period" => self.atr_period.as_ref(),
            "tsl_psar_af0" => self.tsl_psar_af0.as_ref(),
            "tsl_psar_af_step" => self.tsl_psar_af_step.as_ref(),
            "tsl_psar_max_af" => self.tsl_psar_max_af.as_ref(),
            _ => None,
        }
    }

    /// 获取可优化参数的可变引用
    pub fn get_optimizable_param_mut(&mut self, name: &str) -> Option<&mut Param> {
        match name {
            "sl_pct" => self.sl_pct.as_mut(),
            "tp_pct" => self.tp_pct.as_mut(),
            "tsl_pct" => self.tsl_pct.as_mut(),
            "sl_atr" => self.sl_atr.as_mut(),
            "tp_atr" => self.tp_atr.as_mut(),
            "tsl_atr" => self.tsl_atr.as_mut(),
            "atr_period" => self.atr_period.as_mut(),
            "tsl_psar_af0" => self.tsl_psar_af0.as_mut(),
            "tsl_psar_af_step" => self.tsl_psar_af_step.as_mut(),
            "tsl_psar_max_af" => self.tsl_psar_max_af.as_mut(),
            _ => None,
        }
    }

    /// 获取所有可优化参数名称
    pub const OPTIMIZABLE_PARAMS: &'static [&'static str] = &[
        "sl_pct",
        "tp_pct",
        "tsl_pct",
        "sl_atr",
        "tp_atr",
        "tsl_atr",
        "atr_period",
        "tsl_psar_af0",
        "tsl_psar_af_step",
        "tsl_psar_max_af",
    ];

    /// 验证所有参数的有效性。
    /// 返回 `Ok(())` 如果所有参数有效，否则返回详细的错误信息 `BacktestError::InvalidParameter`。
    /// 注意：基本参数验证已在 FromPyObject 实现中进行，此方法主要用于运行时验证。
    pub fn validate(&self) -> Result<(), BacktestError> {
        use crate::types::utils::{check_valid_f64, check_valid_param};

        // 0. 检查所有参数是否为 NaN 或无穷大
        // 检查 f64 类型参数
        let f64_params = [
            ("initial_capital", self.initial_capital),
            ("fee_fixed", self.fee_fixed),
            ("fee_pct", self.fee_pct),
        ];
        for (name, value) in &f64_params {
            check_valid_f64(*value, name)?;
        }

        // 检查 Option<Param> 类型参数
        let param_params = [
            ("sl_pct", &self.sl_pct),
            ("tp_pct", &self.tp_pct),
            ("tsl_pct", &self.tsl_pct),
            ("sl_atr", &self.sl_atr),
            ("tp_atr", &self.tp_atr),
            ("tsl_atr", &self.tsl_atr),
            ("atr_period", &self.atr_period),
        ];
        for (name, param) in &param_params {
            check_valid_param(param, name)?;
        }

        // 1. 验证initial_capital > 0
        if self.initial_capital <= 0.0 {
            return Err(BacktestError::InvalidParameter {
                param_name: "initial_capital".to_string(),
                value: self.initial_capital.to_string(),
                reason: "初始本金必须大于0".to_string(),
            });
        }

        // 2. 验证手续费参数 >= 0
        if self.fee_fixed < 0.0 {
            return Err(BacktestError::InvalidParameter {
                param_name: "fee_fixed".to_string(),
                value: self.fee_fixed.to_string(),
                reason: "固定手续费不能为负".to_string(),
            });
        }

        if self.fee_pct < 0.0 {
            return Err(BacktestError::InvalidParameter {
                param_name: "fee_pct".to_string(),
                value: self.fee_pct.to_string(),
                reason: "百分比手续费不能为负".to_string(),
            });
        }

        // 3. 验证触发模式和 exit_in_bar 的组合
        // 如果 sl_exit_in_bar 为 true，则 sl_trigger_mode 不能为 false (Close 模式)
        if self.sl_exit_in_bar && !self.sl_trigger_mode {
            return Err(BacktestError::InvalidParameter {
                param_name: "sl_exit_in_bar".to_string(),
                value: "true".to_string(),
                reason: "sl_exit_in_bar 不能在 sl_trigger_mode 为 false (Close 模式) 时启用"
                    .to_string(),
            });
        }

        // 如果 tp_exit_in_bar 为 true，则 tp_trigger_mode 不能为 false (Close 模式)
        if self.tp_exit_in_bar && !self.tp_trigger_mode {
            return Err(BacktestError::InvalidParameter {
                param_name: "tp_exit_in_bar".to_string(),
                value: "true".to_string(),
                reason: "tp_exit_in_bar 不能在 tp_trigger_mode 为 false (Close 模式) 时启用"
                    .to_string(),
            });
        }

        Ok(())
    }
}

#[gen_stub_pyclass]
#[pyclass(get_all, set_all)]
#[derive(Debug, Clone, Default)]
pub struct PerformanceParams {
    pub metrics: Vec<PerformanceMetric>,
    pub risk_free_rate: f64,
    pub leverage_safety_factor: Option<f64>,
}

#[gen_stub_pymethods]
#[pymethods]
impl PerformanceParams {
    #[new]
    #[pyo3(signature = (*, metrics=None, risk_free_rate=0.0, leverage_safety_factor=None))]
    pub fn new(
        metrics: Option<Vec<PerformanceMetric>>,
        risk_free_rate: f64,
        leverage_safety_factor: Option<f64>,
    ) -> Self {
        Self {
            metrics: metrics.unwrap_or_default(),
            risk_free_rate,
            leverage_safety_factor,
        }
    }

    /// 业务层设置绩效指标列表。
    pub fn apply_metrics(&mut self, metrics: Vec<PerformanceMetric>) {
        self.metrics = metrics;
    }

    /// 业务层设置无风险利率。
    pub fn apply_risk_free_rate(&mut self, value: f64) {
        self.risk_free_rate = value;
    }

    /// 业务层设置杠杆安全系数。
    pub fn apply_leverage_safety_factor(&mut self, value: Option<f64>) {
        self.leverage_safety_factor = value;
    }
}

#[gen_stub_pyclass]
#[pyclass(get_all, set_all)]
#[derive(Debug, Clone, Default)]
pub struct SingleParamSet {
    pub indicators: HashMap<String, HashMap<String, HashMap<String, Param>>>,
    pub signal: HashMap<String, Param>,
    pub backtest: BacktestParams,
    pub performance: PerformanceParams,
}

#[gen_stub_pymethods]
#[pymethods]
impl SingleParamSet {
    #[new]
    #[pyo3(signature = (*, indicators=None, signal=None, backtest=None, performance=None))]
    pub fn new(
        indicators: Option<HashMap<String, HashMap<String, HashMap<String, Param>>>>,
        signal: Option<HashMap<String, Param>>,
        backtest: Option<BacktestParams>,
        performance: Option<PerformanceParams>,
    ) -> Self {
        Self {
            indicators: indicators.unwrap_or_default(),
            signal: signal.unwrap_or_default(),
            backtest: backtest.unwrap_or_default(),
            performance: performance.unwrap_or_default(),
        }
    }

    /// 业务层一次性替换指标参数容器。
    pub fn set_indicators_params(&mut self, indicators: IndicatorsParams) {
        self.indicators = indicators;
    }

    /// 业务层一次性替换信号参数容器。
    pub fn set_signal_params(&mut self, signal: SignalParams) {
        self.signal = signal;
    }

    /// 业务层一次性替换回测参数容器。
    pub fn set_backtest_params(&mut self, backtest: BacktestParams) {
        self.backtest = backtest;
    }

    /// 业务层一次性替换绩效参数容器。
    pub fn set_performance_params(&mut self, performance: PerformanceParams) {
        self.performance = performance;
    }

    /// 业务层设置单个指标参数，按 data_key/indicator/param_name 精确落位。
    pub fn set_indicator_param(
        &mut self,
        data_key: String,
        indicator_name: String,
        param_name: String,
        param: Param,
    ) {
        self.indicators
            .entry(data_key)
            .or_default()
            .entry(indicator_name)
            .or_default()
            .insert(param_name, param);
    }

    /// 业务层设置单个信号参数。
    pub fn set_signal_param(&mut self, name: String, param: Param) {
        self.signal.insert(name, param);
    }

    /// 业务层设置回测可优化参数（Option<Param> 字段）。
    pub fn set_backtest_optimizable_param(
        &mut self,
        name: &str,
        value: Option<Param>,
    ) -> PyResult<()> {
        self.backtest.set_optimizable_param(name, value)
    }

    /// 业务层设置回测布尔参数。
    pub fn set_backtest_bool_param(&mut self, name: &str, value: bool) -> PyResult<()> {
        self.backtest.set_bool_param(name, value)
    }

    /// 业务层设置回测数值参数。
    pub fn set_backtest_f64_param(&mut self, name: &str, value: f64) -> PyResult<()> {
        self.backtest.set_f64_param(name, value)
    }

    /// 业务层设置绩效指标列表。
    pub fn set_performance_metrics(&mut self, metrics: Vec<PerformanceMetric>) {
        self.performance.apply_metrics(metrics);
    }

    /// 业务层设置绩效无风险利率。
    pub fn set_performance_risk_free_rate(&mut self, value: f64) {
        self.performance.apply_risk_free_rate(value);
    }

    /// 业务层设置杠杆安全系数。
    pub fn set_performance_leverage_safety_factor(&mut self, value: Option<f64>) {
        self.performance.apply_leverage_safety_factor(value);
    }
}

pub type ParamContainer = Vec<SingleParamSet>;

impl Default for BacktestParams {
    fn default() -> Self {
        Self {
            sl_pct: None,
            tp_pct: None,
            tsl_pct: None,
            sl_atr: None,
            tp_atr: None,
            tsl_atr: None,
            atr_period: None,
            tsl_psar_af0: None,
            tsl_psar_af_step: None,
            tsl_psar_max_af: None,
            tsl_atr_tight: false,
            sl_exit_in_bar: true,
            tp_exit_in_bar: true,
            sl_trigger_mode: true,
            tp_trigger_mode: true,
            tsl_trigger_mode: true,
            sl_anchor_mode: false,
            tp_anchor_mode: false,
            tsl_anchor_mode: false,
            initial_capital: 10000.0,
            fee_fixed: 0.0,
            fee_pct: 0.0006,
        }
    }
}
