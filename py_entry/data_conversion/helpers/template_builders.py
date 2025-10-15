"""模版快速构建辅助函数"""

from typing import Union, Optional

from ..input import SignalGroup, RiskRule, Param
from ..input import SignalCondition, RiskCondition
from typing import List


def create_param(
    initial_value: int | float,
    initial_min: Optional[int | float] = None,
    initial_max: Optional[int | float] = None,
    initial_step: Optional[int | float] = None,
    optimize: bool = False,
) -> Param:
    if initial_min is None:
        initial_min = initial_value / 2
    if initial_max is None:
        initial_max = initial_value * 2
    if initial_step is None:
        initial_step = (initial_max - initial_min) / 2
    return Param(
        initial_value=float(initial_value),
        initial_min=float(initial_min),
        initial_max=float(initial_max),
        initial_step=float(initial_step),
        optimize=optimize,
    )


def create_signal_group(
    logic: str, target: str, conditions: List[SignalCondition]
) -> SignalGroup:
    """创建信号组"""
    return SignalGroup(logic=logic, target=target, conditions=conditions)


def create_risk_rule(
    logic: str, target: str, conditions: List[RiskCondition]
) -> RiskRule:
    """创建风险规则"""
    return RiskRule(logic=logic, target=target, conditions=conditions)
