from enum import Enum
from typing import List, Optional
from pydantic import BaseModel


class LogicOp(str, Enum):
    AND = "and"
    OR = "or"


class SignalGroup(BaseModel):
    logic: LogicOp
    comparisons: List[str] = []
    sub_groups: List["SignalGroup"] = []


class SignalTemplate(BaseModel):
    entry_long: Optional[SignalGroup] = None
    exit_long: Optional[SignalGroup] = None
    entry_short: Optional[SignalGroup] = None
    exit_short: Optional[SignalGroup] = None


class TemplateContainer(BaseModel):
    signal: SignalTemplate
