"""参数集定义"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional
from .param import Param

# Type Aliases - 对应 Rust 的 type alias
IndicatorsParams = Dict[str, Dict[str, Dict[str, Param]]]
SignalParams = Dict[str, Param]


class PerformanceMetric(str, Enum):
    TOTAL_RETURN = "total_return"
    SHARPE_RATIO = "sharpe_ratio"
    MAX_DRAWDOWN = "max_drawdown"


@dataclass
class BacktestParams:
    """回测参数 - 对应 Rust BacktestParams struct"""

    # === 资金管理 ===
    # 初始本金。回测开始时的账户资金量 (USD)。
    # 必须大于 0.0。
    initial_capital: float

    # === 手续费 ===
    # 固定手续费。每笔交易的固定手续费金额 (USD)。
    # 必须 >= 0.0。
    fee_fixed: float
    # 百分比手续费。每笔交易金额的百分比手续费。
    # 必须 >= 0.0。
    fee_pct: float

    # 暂停开仓阈值。当账户净值从历史最高点回撤达到此百分比时，暂停所有新开仓。
    pause_drawdown: Param
    # 暂停开仓阈值。当账户净值小于账户净值的sma时,暂停所有新开仓
    pause_sma: Param
    # 暂停开仓阈值。当账户净值小于账户净值的ema时,暂停所有新开仓
    pause_ema: Param

    # === 离场方式 ===
    # 离场时机选择。
    # `true` 表示在当前K线内部触发条件时立即离场。
    # `false` 表示延迟到下一根K线的开盘价离场。
    exit_in_bar: bool

    # exit_in_bar只覆盖sl,tp, exit_in_bar_fallback定义exit_in_bar不覆盖时的行为
    exit_in_bar_fallback: bool

    # === 跟踪止损选项 ===
    # 跟踪止损更新方式。
    # `true` 表示每根K线都更新跟踪止损价格。
    # `false` 表示只在突破高点或低点时才更新跟踪止损价格。
    tsl_per_bar_update: bool

    # === 止损止盈参数 (百分比) ===
    # 百分比止损阈值。当仓位亏损达到此百分比时触发止损。
    # 如果值 <= 0.0，则不使用百分比止损功能。
    sl_pct: Optional[Param] = None
    # 百分比止盈阈值。当仓位盈利达到此百分比时触发止盈。
    # 如果值 <= 0.0，则不使用百分比止盈功能。
    tp_pct: Optional[Param] = None
    # 百分比跟踪止损阈值。当仓位盈利回撤达到此百分比时触发跟踪止损。
    # 如果值 <= 0.0，则不使用百分比跟踪止损功能。
    tsl_pct: Optional[Param] = None

    # === ATR止损止盈参数 ===
    # ATR止损倍数。止损价格基于入场价格减去ATR值乘以该倍数。
    # 如果值 <= 0.0，则不使用ATR止损功能。
    # 依赖 `atr_period`，如果 `atr_period` <= 0.0，即使 `sl_atr` > 0.0 也不会启用。
    sl_atr: Optional[Param] = None
    # ATR止盈倍数。止盈价格基于入场价格加上ATR值乘以该倍数。
    # 如果值 <= 0.0，则不使用ATR止盈功能。
    # 依赖 `atr_period`，如果 `atr_period` <= 0.0，即使 `tp_atr` > 0.0 也不会启用。
    tp_atr: Optional[Param] = None
    # ATR跟踪止损倍数。跟踪止损价格基于最高价减去ATR值乘以该倍数。
    # 如果值 <= 0.0，则不使用ATR跟踪止损功能。
    # 依赖 `atr_period`，如果 `atr_period` <= 0.0，即使 `tsl_atr` > 0.0 也不会启用。
    tsl_atr: Optional[Param] = None
    # ATR计算周期。用于计算平均真实范围 (ATR) 的K线周期数。
    # 如果值 <= 0.0，则所有ATR相关的止损止盈功能都不会启用。
    atr_period: Optional[Param] = None


@dataclass
class PerformanceParams:
    """性能参数 - 对应 Rust PerformanceParams"""

    metrics: List[PerformanceMetric]


@dataclass
class SingleParamSet:
    """单个参数集 - 对应 Rust ProcessedSingleParam"""

    indicators: IndicatorsParams
    signal: SignalParams
    backtest: BacktestParams
    performance: PerformanceParams


ParamContainer = List[SingleParamSet]
