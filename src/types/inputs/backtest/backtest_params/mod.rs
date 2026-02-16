use crate::types::Param;
use pyo3::prelude::*;
use pyo3_stub_gen::derive::*;

mod accessors;
mod defaults;
mod pyo_methods;
mod validation;

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
