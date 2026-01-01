from enum import Enum
from pydantic import BaseModel


class ExecutionStage(str, Enum):
    NONE = "none"
    INDICATOR = "indicator"
    SIGNALS = "signals"
    BACKTEST = "backtest"
    PERFORMANCE = "performance"


class SettingContainer(BaseModel):
    execution_stage: ExecutionStage = ExecutionStage.PERFORMANCE
    return_only_final: bool = False
