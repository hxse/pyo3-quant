"""操作数定义"""

from dataclasses import dataclass


@dataclass
class ParamOperand:
    """参数操作数 - 对应 Rust ParamOperand"""

    source: str


@dataclass
class SignalDataOperand:
    """信号数据操作数 - 对应 Rust SignalDataOperand"""

    source: str
    offset: int
    mtf: int


@dataclass
class RiskDataOperand:
    """风险数据操作数 - 对应 Rust RiskDataOperand"""

    source: str
