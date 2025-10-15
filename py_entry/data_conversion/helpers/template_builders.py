"""模版快速构建辅助函数"""

from typing import Union

from ..input import SignalGroup, RiskRule, Param
from ..input import SignalCondition, RiskCondition
from typing import List


def create_param(
    initial_value: Union[int, float],
    initial_min: Union[int, float],
    initial_max: Union[int, float],
    initial_step: Union[int, float],
    optimize: bool = False,
) -> Param:
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
