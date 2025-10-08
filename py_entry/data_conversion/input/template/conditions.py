"""条件和比较操作符"""

from dataclasses import dataclass
from typing import Optional
from enum import Enum
from .operands import ParamOperand, SignalDataOperand, RiskDataOperand


class CompareOp(Enum):
    """比较操作符 - 对应 Rust CompareOp"""

    GT = "GT"
    LT = "LT"
    CGT = "CGT"
    CLT = "CLT"
    GE = "GE"
    LE = "LE"
    EQ = "EQ"
    NE = "NE"


@dataclass
class SignalCondition:
    """信号条件 - 对应 Rust SignalCondition"""

    compare: CompareOp
    a_data: Optional[SignalDataOperand] = None
    a_param: Optional[ParamOperand] = None
    b_data: Optional[SignalDataOperand] = None
    b_param: Optional[ParamOperand] = None


@dataclass
class RiskCondition:
    """风险条件 - 对应 Rust RiskCondition"""

    compare: CompareOp
    a_data: Optional[RiskDataOperand] = None
    a_param: Optional[ParamOperand] = None
    b_data: Optional[RiskDataOperand] = None
    b_param: Optional[ParamOperand] = None
