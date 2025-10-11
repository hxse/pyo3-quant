"""模版快速构建辅助函数"""

from ..input import (
    SignalGroup,
    RiskRule,
    SignalTemplate,
    RiskTemplate,
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


def create_signal_template(name: str, groups: List[SignalGroup]) -> SignalTemplate:
    """创建信号模版"""
    return SignalTemplate(name=name, template=groups)


def create_risk_template(name: str, rules: List[RiskRule]) -> RiskTemplate:
    """创建风险模版"""
    return RiskTemplate(name=name, template=rules)
