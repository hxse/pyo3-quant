"""模板定义"""

from dataclasses import dataclass
from typing import List
from .conditions import SignalCondition, RiskCondition
from typing import Optional


@dataclass
class SignalGroup:
    """信号组 - 对应 Rust SignalGroup"""

    logic: str
    conditions: List[SignalCondition]


@dataclass
class SignalTemplate:
    """信号模板 - 对应 Rust SignalTemplate"""

    name: str
    enter_long: Optional[SignalGroup] = None
    exit_long: Optional[SignalGroup] = None
    enter_short: Optional[SignalGroup] = None
    exit_short: Optional[SignalGroup] = None


@dataclass
class RiskGroup:
    """风险规则 - 对应 Rust RiskRule"""

    logic: str
    conditions: List[RiskCondition]


@dataclass
class RiskTemplate:
    """风险模板 - 对应 Rust RiskTemplate"""

    name: str
    size_neutral_pct: Optional[RiskGroup] = None
    size_up_pct: Optional[RiskGroup] = None
    size_down_pct: Optional[RiskGroup] = None
    size_skip_pct: Optional[RiskGroup] = None


@dataclass
class TemplateConfig:
    """模板配置 - 包装 signal 和 risk"""

    signal: SignalTemplate
    risk: RiskTemplate
