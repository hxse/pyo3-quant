"""
图表系列选项类型定义

本模块定义了所有图表类型的详细选项，完全符合前端 Lightweight Charts 的配置要求。
每个选项类都使用 dataclass，支持序列化为 JSON 配置文件。
"""

from dataclasses import dataclass, asdict
from typing import Optional, Union
from enum import IntEnum


# =============================================================================
# 枚举类型
# =============================================================================


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


# =============================================================================
# 选项类定义
# =============================================================================


@dataclass
class CandleOption:
    """
    蜡烛图选项

    用于配置 K 线图的颜色和样式。
    """

    upColor: Optional[str] = None  # 上涨蜡烛颜色，默认 "#26a69a"
    downColor: Optional[str] = None  # 下跌蜡烛颜色，默认 "#ef5350"
    wickUpColor: Optional[str] = None  # 上涨影线颜色，默认同 upColor
    wickDownColor: Optional[str] = None  # 下跌影线颜色，默认同 downColor
    borderVisible: Optional[bool] = None  # 是否显示边框，默认 True
    borderUpColor: Optional[str] = None  # 上涨边框颜色，默认同 upColor
    borderDownColor: Optional[str] = None  # 下跌边框颜色，默认同 downColor
    wickVisible: Optional[bool] = None  # 是否显示影线，默认 True

    def to_dict(self):
        """转换为字典，移除 None 值"""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class LineOption:
    """
    折线图选项

    用于配置普通指标线的颜色、宽度和样式。
    """

    color: Optional[str] = None  # 线条颜色，默认 "#2962FF"
    lineWidth: Optional[int] = None  # 线条宽度（像素），默认 3
    lineStyle: Optional[int] = None  # 线条样式（LineStyle 枚举），默认 0 (Solid)
    lineType: Optional[int] = None  # 线条类型（LineType 枚举），默认 0 (Simple)
    lineVisible: Optional[bool] = None  # 是否显示线条，默认 True
    pointMarkersVisible: Optional[bool] = None  # 是否显示数据点标记，默认 False
    crosshairMarkerVisible: Optional[bool] = None  # 是否显示十字光标标记，默认 True

    def to_dict(self):
        """转换为字典，移除 None 值"""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class HistogramOption:
    """
    直方图选项

    用于配置成交量等柱状图的颜色和基线。
    """

    color: Optional[str] = None  # 柱子颜色，默认 "#26a69a"
    base: Optional[float] = None  # 基线值，默认 0

    def to_dict(self):
        """转换为字典，移除 None 值"""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class VolumeOption:
    """
    成交量选项

    用于配置成交量柱状图的显示。
    前端会自动根据OHLC数据设置涨跌颜色，自动应用叠加层配置。
    """

    priceScaleMarginTop: Optional[float] = None  # 叠加层顶部边距(0-1)，默认 0.7
    adjustMainSeries: Optional[bool] = None  # 是否自动调整主系列避免重叠，默认 True

    def to_dict(self):
        """转换为字典，移除 None 值"""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class AreaOption:
    """
    面积图选项

    用于配置面积图的渐变填充和边线样式。
    """

    topColor: Optional[str] = (
        None  # 面积顶部颜色（建议RGBA），默认 "rgba(41, 98, 255, 0.28)"
    )
    bottomColor: Optional[str] = (
        None  # 面积底部颜色（建议RGBA），默认 "rgba(41, 98, 255, 0.05)"
    )
    lineColor: Optional[str] = None  # 边线颜色，默认 "#2962FF"
    lineWidth: Optional[int] = None  # 边线宽度，默认 3
    lineStyle: Optional[int] = None  # 边线样式（LineStyle 枚举），默认 0 (Solid)

    def to_dict(self):
        """转换为字典，移除 None 值"""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class BaselineOption:
    """
    基线图选项

    用于配置基线图，显示价格相对于基线的上下波动。
    """

    baseValue: Optional[float] = None  # 基线值，默认 0
    topLineColor: Optional[str] = None  # 基线上方线条颜色，默认 "#26a69a"
    bottomLineColor: Optional[str] = None  # 基线下方线条颜色，默认 "#ef5350"
    topFillColor1: Optional[str] = (
        None  # 上方填充颜色1（顶部），默认 "rgba(38, 166, 154, 0.28)"
    )
    topFillColor2: Optional[str] = (
        None  # 上方填充颜色2（基线），默认 "rgba(38, 166, 154, 0.05)"
    )
    bottomFillColor1: Optional[str] = (
        None  # 下方填充颜色1（基线），默认 "rgba(239, 83, 80, 0.05)"
    )
    bottomFillColor2: Optional[str] = (
        None  # 下方填充颜色2（底部），默认 "rgba(239, 83, 80, 0.28)"
    )
    lineWidth: Optional[int] = None  # 线条宽度，默认 3
    lineStyle: Optional[int] = None  # 线条样式（LineStyle 枚举），默认 0 (Solid)

    def to_dict(self):
        """转换为字典，移除 None 值"""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class BarOption:
    """
    条形图选项

    用于配置 OHLC 条形图（与 Candle 类似但显示为条形）。
    """

    upColor: Optional[str] = None  # 上涨条形颜色，默认 "#26a69a"
    downColor: Optional[str] = None  # 下跌条形颜色，默认 "#ef5350"
    openVisible: Optional[bool] = None  # 是否显示开盘价刻度，默认 True
    thinBars: Optional[bool] = None  # 是否使用细条形，默认 False

    def to_dict(self):
        """转换为字典，移除 None 值"""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class HorizontalLineOption:
    """
    水平参考线选项

    用于配置水平参考线（如 RSI 的 30/70 线）。
    不需要数据源，只需要配置参数。
    """

    value: float  # 水平线的价格值（必填）
    color: str  # 线条颜色（必填）
    label: Optional[str] = None  # 标签文本（可选）
    showLabel: bool = False  # 是否显示标签，默认 False

    def to_dict(self):
        """转换为字典，移除 None 值"""
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class VerticalLineOption:
    """
    垂直参考线选项

    用于配置垂直参考线（如重要事件标记）。
    不需要数据源，只需要配置参数。
    """

    value: Union[int, float, str]  # 时间值（Unix时间戳或日期字符串，必填）
    color: str  # 线条颜色（必填）
    label: Optional[str] = None  # 标签文本（可选）
    showLabel: bool = False  # 是否显示标签，默认 False

    def to_dict(self):
        """转换为字典，移除 None 值"""
        return {k: v for k, v in asdict(self).items() if v is not None}


# =============================================================================
# 推荐配色方案
# =============================================================================


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
