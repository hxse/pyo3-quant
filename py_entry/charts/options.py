"""
图表系列选项类型定义

本模块从 py_entry.types.chart_config 重新导出选项类，保持向后兼容。
"""

# 重新导出所有选项类
from py_entry.types.chart_config import (
    CandleOption,
    LineOption,
    HistogramOption,
    VolumeOption,
    AreaOption,
    BaselineOption,
    BarOption,
    HorizontalLineOption,
    VerticalLineOption,
)

# ColorSchemes 可以保留在这里
from enum import IntEnum


class LineStyle(IntEnum):
    """线条样式枚举"""

    Solid = 0  # 实线（推荐）
    Dotted = 1  # 点线
    Dashed = 2  # 虚线
    LargeDashed = 3  # 大虚线
    SparseDotted = 4  # 稀疏点线


class LineType(IntEnum):
    """线条类型枚举"""

    Simple = 0  # 简单连接（推荐）
    WithSteps = 1  # 阶梯式
    Curved = 2  # 平滑曲线


class ColorSchemes:
    """预定义的配色方案"""

    # 经典配色
    CLASSIC = {
        "green": "#26a69a",  # 上涨/正值
        "red": "#ef5350",  # 下跌/负值
        "blue": "#1f77b4",  # 主要指标
        "orange": "#ff7f0e",  # 次要指标
        "purple": "#9467bd",  # 辅助指标
        "yellow": "#faad14",  # 警告/中性
        "gray": "#808080",  # 零线
    }

    # Matplotlib 风格（多条线时使用）
    MATPLOTLIB = [
        "#1f77b4",
        "#ff7f0e",
        "#2ca02c",
        "#d62728",
        "#9467bd",
        "#8c564b",
        "#e377c2",
        "#7f7f7f",
        "#bcbd22",
        "#17becf",
    ]

    @classmethod
    def get_line_color(cls, index: int) -> str:
        """根据索引获取线条颜色（循环使用 Matplotlib 配色）"""
        return cls.MATPLOTLIB[index % len(cls.MATPLOTLIB)]


__all__ = [
    "CandleOption",
    "LineOption",
    "HistogramOption",
    "VolumeOption",
    "AreaOption",
    "BaselineOption",
    "BarOption",
    "HorizontalLineOption",
    "VerticalLineOption",
    "LineStyle",
    "LineType",
    "ColorSchemes",
]
