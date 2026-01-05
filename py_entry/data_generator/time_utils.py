"""
时间处理工具模块
"""

from datetime import datetime, timezone

time_format = "%Y-%m-%dT%H:%M:%S%.3f%Z"
fixed_cols = ["time", "date"]


def get_utc_timestamp_ms(time_str: str) -> int:
    """
    将 ISO 时间字符串转换为 UTC 毫秒时间戳
    例如: "2025-01-01T00:00:00" -> 1735689600000
    """
    ts = datetime.fromisoformat(time_str).replace(tzinfo=timezone.utc).timestamp()
    return int(ts * 1000)


def parse_timeframe(tf: str) -> int:
    """
    将时间周期字符串转换为毫秒数

    Args:
        tf: 时间周期字符串,如 "15m", "1h", "4h", "1d"

    Returns:
        毫秒数
    """
    unit = tf[-1]
    value = int(tf[:-1])

    if unit == "m":
        return value * 60 * 1000
    elif unit == "h":
        return value * 60 * 60 * 1000
    elif unit == "d":
        return value * 24 * 60 * 60 * 1000
    else:
        raise ValueError(f"不支持的时间周期单位: {unit}")
