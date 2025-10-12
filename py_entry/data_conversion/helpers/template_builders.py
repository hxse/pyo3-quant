"""模版快速构建辅助函数"""

from ..input import (
    SignalGroup,
    RiskRule,
)
from ..input import SignalCondition, RiskCondition
from typing import List


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
