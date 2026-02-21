from enum import Enum


class LogLevel(str, Enum):
    """结果日志输出级别。"""

    BRIEF = "brief"
    DETAILED = "detailed"
