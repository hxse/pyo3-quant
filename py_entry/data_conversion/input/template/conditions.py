"""条件和比较操作符"""

from dataclasses import dataclass
from enum import Enum
from .operands import (
    SignalDataOperand,
    SignalRightOperand,
)


class CompareOp(str, Enum):
    """比较操作符 - 对应 Rust CompareOp"""

    GT = "GT"  # >
    LT = "LT"  # <
    GE = "GE"  # >=
    LE = "LE"  # <=
    EQ = "EQ"  # ==
    NE = "NE"  # !=
    CGT = "CGT"  # > 交叉
    CLT = "CLT"  # < 交叉
    CGE = "CGE"  # >= 交叉
    CLE = "CLE"  # <= 交叉
    CEQ = "CEQ"  # == 交叉
    CNE = "CNE"  # != 交叉


class LogicOp(str, Enum):
    """逻辑操作符 - 对应 Rust LogicOp"""

    AND = "and"
    OR = "or"


@dataclass
class SignalCondition:
    """信号条件 - 对应 Rust SignalCondition"""

    a: SignalDataOperand
    b: SignalRightOperand
    compare: CompareOp
