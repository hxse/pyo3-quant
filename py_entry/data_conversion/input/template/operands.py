from dataclasses import dataclass
from typing import Union, Literal


@dataclass
class ParamOperand:
    name: str
    _tag: Literal["Param"] = "Param"


@dataclass
class SignalDataOperand:
    name: str
    source: str
    source_idx: int
    offset: int
    _tag: Literal["Data"] = "Data"


@dataclass
class RiskDataOperand:
    name: str
    source: str
    _tag: Literal["Data"] = "Data"


SignalRightOperand = Union[SignalDataOperand, ParamOperand]
RiskRightOperand = Union[RiskDataOperand, ParamOperand]
