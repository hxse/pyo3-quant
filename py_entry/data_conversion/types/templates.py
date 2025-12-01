"""模板定义"""

from dataclasses import dataclass, field
from typing import List, Optional
from .conditions import SignalCondition, LogicOp


@dataclass
class SignalGroup:
    """信号组 - 对应 Rust SignalGroup"""

    logic: LogicOp
    comparisons: List[str] = field(default_factory=list)
    sub_groups: List["SignalGroup"] = field(default_factory=list)


@dataclass
class SignalTemplate:
    """信号模板 - 对应 Rust SignalTemplate"""

    name: str
    enter_long: Optional[SignalGroup] = None
    exit_long: Optional[SignalGroup] = None
    enter_short: Optional[SignalGroup] = None
    exit_short: Optional[SignalGroup] = None


@dataclass
class TemplateContainer:
    """模板配置 - 包装 signal"""

    signal: SignalTemplate
