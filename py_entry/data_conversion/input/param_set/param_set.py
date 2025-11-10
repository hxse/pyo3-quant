"""参数集定义"""

from dataclasses import dataclass
from enum import Enum
from typing import Dict, List, Optional
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

    tsl_use_high: bool
    tsl_per_bar_update: bool
    exit_in_bar: bool

    initial_capital: float
    stop_pct: Param
    resume_pct: Param

    fee_fixed: float
    fee_pct: float

    sl_pct: Optional[Param] = None
    tp_pct: Optional[Param] = None
    tsl_pct: Optional[Param] = None

    sl_atr: Optional[Param] = None
    tp_atr: Optional[Param] = None
    tsl_atr: Optional[Param] = None
    atr_period: Optional[Param] = None


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
