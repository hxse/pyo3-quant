from typing import TYPE_CHECKING
import pandas as pd

if TYPE_CHECKING:
    from .config import TimeframeConfig

# === 工具函数 ===


def get_largest_timeframe_index(
    klines_list: list[tuple["TimeframeConfig", pd.DataFrame]],
) -> tuple[int, int]:
    """
    找到列表中最大周期的索引和秒数

    Returns:
        (index, seconds)
    """
    if not klines_list:
        return -1, 0

    max_seconds = -1
    max_idx = -1

    for i, (tf, _) in enumerate(klines_list):
        if tf.seconds > max_seconds:
            max_seconds = tf.seconds
            max_idx = i

    return max_idx, max_seconds


def get_base_timeframe_config(timeframes: list["TimeframeConfig"]) -> "TimeframeConfig":
    """获取基础周期（最小周期），用于触发扫描"""
    if not timeframes:
        raise ValueError("Config timeframes is empty")
    return min(timeframes, key=lambda x: x.seconds)
