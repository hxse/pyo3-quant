"""回测配置"""

from dataclasses import dataclass
from enum import Enum


class ExecutionStage(str, Enum):
    """执行阶段枚举 - 对应 Rust ExecutionStage"""

    NONE = "none"
    INDICATOR = "indicator"
    SIGNALS = "signals"
    BACKTEST = "backtest"
    PERFORMANCE = "performance"


@dataclass
class SettingContainer:
    """回测配置 - 对应 Rust ProcessedSettings"""

    execution_stage: ExecutionStage = ExecutionStage.PERFORMANCE
    return_only_final: bool = False
