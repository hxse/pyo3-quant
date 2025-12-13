"""
图表配置通用辅助工具

提供通用工具函数，并重新导出其他模块的函数以保持向后兼容性。
"""

from typing import Dict, Any

from .options import ColorSchemes

# 为了保持向后兼容，重新导出其他模块的函数
from .series_builders import (
    create_candle_series,
    create_line_series,
    create_histogram_series,
    create_volume_series,
    create_area_series,
    create_baseline_series,
    create_bar_series,
    create_hline,
    create_vline,
)

from .core_helpers import (
    get_style_option,
    init_counter,
    match_indicator_columns,
    match_indicator_column,
)

# 暴露所有导入的函数
__all__ = [
    # 系列构建器
    "create_candle_series",
    "create_line_series",
    "create_histogram_series",
    "create_volume_series",
    "create_area_series",
    "create_baseline_series",
    "create_bar_series",
    "create_hline",
    "create_vline",
    # 核心辅助函数
    "get_style_option",
    "init_counter",
    "match_indicator_columns",
    "match_indicator_column",
    # 通用工具函数
    "remove_none_values",
    "get_color_for_index",
]


def remove_none_values(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    递归移除字典中的 None 值

    Args:
        data: 输入字典

    Returns:
        移除 None 值后的字典
    """
    if not isinstance(data, dict):
        return data

    return {
        k: remove_none_values(v) if isinstance(v, dict) else v
        for k, v in data.items()
        if v is not None
    }


def get_color_for_index(index: int) -> str:
    """
    根据索引获取推荐的线条颜色

    Args:
        index: 索引值

    Returns:
        颜色字符串
    """
    return ColorSchemes.get_line_color(index)
