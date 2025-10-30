"""模板定义"""

from dataclasses import dataclass
from typing import List, Optional
from .conditions import SignalCondition, RiskCondition, LogicOp


@dataclass
class SignalGroup:
    """信号组 - 对应 Rust SignalGroup"""

    logic: LogicOp
    conditions: List[SignalCondition]


@dataclass
class SignalTemplate:
    """信号模板 - 对应 Rust SignalTemplate"""

    name: str
    enter_long: Optional[List[SignalGroup]] = None
    exit_long: Optional[List[SignalGroup]] = None
    enter_short: Optional[List[SignalGroup]] = None
    exit_short: Optional[List[SignalGroup]] = None


@dataclass
class TemplateContainer:
    """模板配置 - 包装 signal"""

    signal: SignalTemplate
