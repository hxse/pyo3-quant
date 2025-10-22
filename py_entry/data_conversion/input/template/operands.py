"""操作数定义"""

from dataclasses import dataclass


@dataclass
class ParamOperand:
    """参数操作数 - 对应 Rust ParamOperand"""

    name: str


@dataclass
class SignalDataOperand:
    """信号数据操作数 - 对应 Rust SignalDataOperand"""

    name: str
    source: str
    source_idx: int
    offset: int


@dataclass
class RiskDataOperand:
    """风险数据操作数 - 对应 Rust RiskDataOperand"""

    name: str
    source: str
