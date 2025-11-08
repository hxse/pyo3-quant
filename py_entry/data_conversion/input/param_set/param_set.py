"""参数集定义"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List
from .param import Param

# Type Aliases - 对应 Rust 的 type alias
IndicatorsParams = Dict[str, List[Dict[str, Dict[str, Param]]]]
SignalParams = Dict[str, Param]


class PerformanceMetric(str, Enum):
    TOTAL_RETURN = "total_return"
    SHARPE_RATIO = "sharpe_ratio"
    MAX_DRAWDOWN = "max_drawdown"


@dataclass
class BacktestParams:
    """回测参数 - 对应 Rust BacktestParams struct"""

    sl_pct: Param
    tp_pct: Param
    tsl_pct: Param

    sl_atr: Param
    tp_atr: Param
    tsl_atr: Param
    atr_period: Param

    tsl_use_high: bool
    tsl_per_bar_update: bool
    exit_in_bar: bool

    initial_capital: float
    stop_pct: Param
    resume_pct: Param

    fee_fixed: float
    fee_pct: float


@dataclass
class PerformanceParams:
    """性能参数 - 对应 Rust PerformanceParams"""

    metrics: List[PerformanceMetric]


@dataclass
class SingleParamSet:
    """单个参数集 - 对应 Rust ProcessedSingleParam"""

    indicators: IndicatorsParams  # 注意：复数
    signal: SignalParams
    backtest: BacktestParams
    performance: PerformanceParams


ParamContainer = List[SingleParamSet]
