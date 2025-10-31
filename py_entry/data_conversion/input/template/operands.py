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
    offset: int
    _tag: Literal["Data"] = "Data"


SignalRightOperand = Union[SignalDataOperand, ParamOperand]
