"""参数集定义"""

from dataclasses import dataclass
from typing import Dict, List
from .param import Param

# Type Aliases - 对应 Rust 的 type alias
IndicatorsParams = List[Dict[str, Dict[str, Param]]]
SignalParams = Dict[str, Param]
RiskParams = Dict[str, Param]


@dataclass
class BacktestParams:
    """回测参数 - 对应 Rust BacktestParams struct"""

    sl: Param
    tp: Param
    position_pct: Param


@dataclass
class PerformanceParams:
    """性能参数 - 对应 Rust PerformanceParams"""

    metrics: List[str]


@dataclass
class SingleParamSet:
    """单个参数集 - 对应 Rust ProcessedSingleParam"""

    indicators: IndicatorsParams  # 注意：复数
    signal: SignalParams
    backtest: BacktestParams
    risk: RiskParams
    performance: PerformanceParams


@dataclass
class ParamSet:
    """完整参数集列表 - 对应 Rust ProcessedParamSet"""

    params: List[SingleParamSet]
