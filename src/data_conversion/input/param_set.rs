use super::param::Param;
use crate::error::BacktestError;
use pyo3::prelude::*;
use pyo3::Bound;
use std::collections::HashMap;

pub type IndicatorsParams = HashMap<String, Vec<HashMap<String, HashMap<String, Param>>>>;
pub type SignalParams = HashMap<String, Param>;

#[derive(Debug, Clone, Copy, Eq, PartialEq, Hash)]
pub enum PerformanceMetric {
    TotalReturn,
    SharpeRatio,
    MaxDrawdown,
}

impl PerformanceMetric {
    pub fn as_str(&self) -> &'static str {
        match self {
            Self::TotalReturn => "total_return",
            Self::SharpeRatio => "sharpe_ratio",
            Self::MaxDrawdown => "max_drawdown",
        }
    }
}

impl<'source> FromPyObject<'source> for PerformanceMetric {
    fn extract_bound(ob: &Bound<'source, PyAny>) -> PyResult<Self> {
        let s: String = ob.extract()?;
        match s.as_str() {
            "total_return" => Ok(Self::TotalReturn),
            "sharpe_ratio" => Ok(Self::SharpeRatio),
            "max_drawdown" => Ok(Self::MaxDrawdown),
            _ => Err(PyErr::new::<pyo3::exceptions::PyValueError, _>(format!(
                "Unknown metric: {}",
                s
            ))),
        }
    }
}

/// 回测引擎的参数结构体。
/// 包含止损止盈、ATR、资金管理、手续费等所有可配置参数。
/// 参数值为 `Param` 类型，通过 `.value` 访问实际数值。
#[derive(Clone, Debug, FromPyObject)]
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

    // === 跟踪止损选项 ===
    /// 跟踪止损锚点选择。
    /// `true` 表示使用K线的最高价 (high) 作为跟踪止损的锚点。
    /// `false` 表示使用K线的收盘价 (close) 作为跟踪止损的锚点。
    pub tsl_use_high: bool,
    /// 跟踪止损更新方式。
    /// `true` 表示每根K线都更新跟踪止损价格。
    /// `false` 表示只在突破高点或低点时才更新跟踪止损价格。
    pub tsl_per_bar_update: bool,

    // === 离场方式 ===
    /// 离场时机选择。
    /// `true` 表示在当前K线内部触发条件时立即离场。
    /// `false` 表示延迟到下一根K线的开盘价离场。
    pub exit_in_bar: bool,

    // === 资金管理 ===
    /// 初始本金。回测开始时的账户资金量 (USD)。
    /// 必须大于 0.0。
    pub initial_capital: f64,
    /// 暂停开仓阈值。当账户净值从历史最高点回撤达到此百分比时，暂停所有新开仓。
    /// 如果值 <= 0.0，则不使用暂停开仓功能。
    /// 依赖 `resume_pct`，两者必须同时启用或禁用。
    pub stop_pct: Param,
    /// 恢复开仓阈值。当账户净值从最低点恢复达到此百分比时，恢复开仓。
    /// 如果值 <= 0.0，则不使用恢复开仓功能。
    /// 依赖 `stop_pct`，两者必须同时启用或禁用。
    pub resume_pct: Param,

    // === 手续费 ===
    /// 固定手续费。每笔交易的固定手续费金额 (USD)。
    /// 必须 >= 0.0。
    pub fee_fixed: f64,
    /// 百分比手续费。每笔交易金额的百分比手续费。
    /// 必须 >= 0.0。
    pub fee_pct: f64,
}

impl BacktestParams {
    /// 检查sl_pct参数是否有效（不验证其他参数）。
    /// 当 `sl_pct` 存在且其值大于 0.0 时，返回 true。
    pub fn is_sl_pct_param_valid(&self) -> bool {
        self.sl_pct
            .as_ref()
            .map_or(false, |param| param.value > 0.0)
    }

    /// 检查tp_pct参数是否有效（不验证其他参数）。
    /// 当 `tp_pct` 存在且其值大于 0.0 时，返回 true。
    pub fn is_tp_pct_param_valid(&self) -> bool {
        self.tp_pct
            .as_ref()
            .map_or(false, |param| param.value > 0.0)
    }

    /// 检查tsl_pct参数是否有效（不验证其他参数）。
    /// 当 `tsl_pct` 存在且其值大于 0.0 时，返回 true。
    pub fn is_tsl_pct_param_valid(&self) -> bool {
        self.tsl_pct
            .as_ref()
            .map_or(false, |param| param.value > 0.0)
    }

    /// 检查是否有任一百分比参数（sl_pct、tp_pct、tsl_pct）有效。
    pub fn has_any_pct_param(&self) -> bool {
        self.is_sl_pct_param_valid()
            || self.is_tp_pct_param_valid()
            || self.is_tsl_pct_param_valid()
    }

    /// 检查sl_atr参数是否有效（不验证atr_period）。
    /// 当 `sl_atr` 存在且其值大于 0.0 时，返回 true。
    pub fn is_sl_atr_param_valid(&self) -> bool {
        self.sl_atr
            .as_ref()
            .map_or(false, |param| param.value > 0.0)
    }

    /// 检查tp_atr参数是否有效（不验证atr_period）。
    /// 当 `tp_atr` 存在且其值大于 0.0 时，返回 true。
    pub fn is_tp_atr_param_valid(&self) -> bool {
        self.tp_atr
            .as_ref()
            .map_or(false, |param| param.value > 0.0)
    }

    /// 检查tsl_atr参数是否有效（不验证atr_period）。
    /// 当 `tsl_atr` 存在且其值大于 0.0 时，返回 true。
    pub fn is_tsl_atr_param_valid(&self) -> bool {
        self.tsl_atr
            .as_ref()
            .map_or(false, |param| param.value > 0.0)
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
                .map_or(false, |param| param.value > 0.0);

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

    /// 验证所有参数的有效性。
    /// 返回 `Ok(())` 如果所有参数有效，否则返回详细的错误信息 `BacktestError::InvalidParameter`。
    /// 注意：基本参数验证已在 FromPyObject 实现中进行，此方法主要用于运行时验证。
    pub fn validate(&self) -> Result<(), BacktestError> {
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

        // 3. 验证仓位管理参数的一致性
        // 如果启用仓位管理,stop_pct和resume_pct都必须>0
        let stop_enabled = self.stop_pct.value > 0.0;
        let resume_enabled = self.resume_pct.value > 0.0;

        if stop_enabled != resume_enabled {
            return Err(BacktestError::InvalidParameter {
                param_name: "stop_pct/resume_pct".to_string(),
                value: format!(
                    "stop_pct={}, resume_pct={}",
                    self.stop_pct.value, self.resume_pct.value
                ),
                reason: "stop_pct和resume_pct必须同时启用或禁用".to_string(),
            });
        }

        Ok(())
    }
}

#[derive(Debug, Clone, FromPyObject)]
pub struct PerformanceParams {
    pub metrics: Vec<PerformanceMetric>,
}

#[derive(Debug, Clone, FromPyObject)]
pub struct SingleParam {
    pub indicators: IndicatorsParams,
    pub signal: SignalParams,
    pub backtest: BacktestParams,
    pub performance: PerformanceParams,
}

pub type ParamContainer = Vec<SingleParam>;
