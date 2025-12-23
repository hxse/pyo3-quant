"""
时间处理工具模块
"""

time_format = "%Y-%m-%dT%H:%M:%S%.3f%Z"
fixed_cols = ["time", "date"]


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
