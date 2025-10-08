"""模板定义"""

from dataclasses import dataclass
from typing import List
from .conditions import SignalCondition, RiskCondition


@dataclass
class SignalGroup:
    """信号组 - 对应 Rust SignalGroup"""

    logic: str
    target: str
    conditions: List[SignalCondition]


@dataclass
class SignalTemplate:
    """信号模板 - 对应 Rust SignalTemplate"""

    name: str
    template: List[SignalGroup]


@dataclass
class RiskRule:
    """风险规则 - 对应 Rust RiskRule"""

    logic: str
    target: str
    conditions: List[RiskCondition]


@dataclass
class RiskTemplate:
    """风险模板 - 对应 Rust RiskTemplate"""

    name: str
    template: List[RiskRule]


@dataclass
class TemplateConfig:
    """模板配置 - 包装 signal 和 risk"""

    signal: SignalTemplate
    risk: RiskTemplate
