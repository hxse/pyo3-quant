"""模板定义"""

from dataclasses import dataclass, field
from typing import List, Optional

from enum import Enum


class LogicOp(str, Enum):
    """逻辑操作符 - 对应 Rust LogicOp"""

    AND = "and"
    OR = "or"


@dataclass
class SignalGroup:
    """信号组 - 对应 Rust SignalGroup"""

    logic: LogicOp
    comparisons: List[str] = field(default_factory=list)
    sub_groups: List["SignalGroup"] = field(default_factory=list)


@dataclass
class SignalTemplate:
    """信号模板 - 对应 Rust SignalTemplate"""

    enter_long: Optional[SignalGroup] = None
    exit_long: Optional[SignalGroup] = None
    enter_short: Optional[SignalGroup] = None
    exit_short: Optional[SignalGroup] = None


@dataclass
class TemplateContainer:
    """模板配置 - 包装 signal"""

    signal: SignalTemplate
