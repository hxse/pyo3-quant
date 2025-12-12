from dataclasses import dataclass
from typing import List, Literal, TypedDict, Optional, Union

# 导入详细的选项类型定义
try:
    from py_entry.data_conversion.chart_utils.options import (
        CandleOption,
        LineOption,
        HistogramOption,
        AreaOption,
        BaselineOption,
        BarOption,
        HorizontalLineOption,
        VerticalLineOption,
    )
except ImportError:
    # 兼容性：如果新模块不存在，使用简化定义
    @dataclass
    class CandleOption:
        """Candle/OHLC 图表选项"""

        upColor: Optional[str] = None
        downColor: Optional[str] = None
        borderUpColor: Optional[str] = None
        borderDownColor: Optional[str] = None
        wickUpColor: Optional[str] = None
        wickDownColor: Optional[str] = None

    @dataclass
    class HistogramOption:
        """柱状图选项"""

        upColor: Optional[str] = None
        downColor: Optional[str] = None

    @dataclass
    class LineOption:
        """线图选项"""

        color: Optional[str] = None
        lineWidth: Optional[int] = None
        lineStyle: Optional[int] = None

    @dataclass
    class AreaOption:
        """面积图选项"""

        topColor: Optional[str] = None
        bottomColor: Optional[str] = None
        lineColor: Optional[str] = None
        lineWidth: Optional[int] = None
        lineStyle: Optional[int] = None

    @dataclass
    class BaselineOption:
        """基线图选项"""

        baseValue: Optional[float] = None
        topLineColor: Optional[str] = None
        bottomLineColor: Optional[str] = None

    @dataclass
    class BarOption:
        """条形图选项"""

        upColor: Optional[str] = None
        downColor: Optional[str] = None

    @dataclass
    class HorizontalLineOption:
        """水平线选项"""

        color: str
        value: float
        label: Optional[str] = None

    @dataclass
    class VerticalLineOption:
        """垂直线选项"""

        color: str
        value: Union[float, str]
        label: Optional[str] = None


# 向后兼容的别名
HorizontalLine = HorizontalLineOption
VerticalLine = VerticalLineOption

# --- Core Configuration ---


@dataclass
class IndicatorLayoutItem:
    """
    单个指标布局配置项

    用于 INDICATOR_LAYOUT 配置中定义每个指标的显示方式和样式。
    支持为多个同名指标（如多个 sma）配置不同的样式选项。
    """

    indicator: str  # 指标名称，如 "ohlc", "volume", "sma", "rsi" 等
    type: Literal[
        "candle", "histogram", "line", "area", "baseline", "bar", "hline", "vline"
    ]
    show: bool = True

    # 样式选项数组（为多个同名指标提供不同样式）
    # 按照同周期、同窗格的顺序依次分配，数量不够时重复最后一个
    candleOptions: Optional[List[CandleOption]] = None
    histogramOptions: Optional[List[HistogramOption]] = None
    lineOptions: Optional[List[LineOption]] = None
    areaOptions: Optional[List[AreaOption]] = None
    baselineOptions: Optional[List[BaselineOption]] = None
    barOptions: Optional[List[BarOption]] = None

    # 水平线和垂直线选项（通常每个指标只有一个）
    hLineOpt: Optional[HorizontalLineOption] = None
    vLineOpt: Optional[VerticalLineOption] = None

    # 用于 hline 的固定值（如 macd_zero 的 0）
    value: Optional[float] = None


@dataclass
class SeriesItemConfig:
    """
    图表系列配置项

    新架构说明：
    - 面板位置由数组顺序隐式表达，不需要 position 字段
    - 选项命名与 type 字段保持一致（candleOpt, histogramOpt, lineOpt 等）
    """

    type: Literal[
        "candle", "histogram", "line", "area", "baseline", "bar", "hline", "vline"
    ]
    show: bool = True

    # 数据源字段
    fileName: Optional[str] = None
    dataName: Optional[Union[str, List[str]]] = None

    # 样式选项（根据 type 选择对应的选项）
    candleOpt: Optional[CandleOption] = None
    histogramOpt: Optional[HistogramOption] = None
    lineOpt: Optional[LineOption] = None
    areaOpt: Optional[AreaOption] = None
    baselineOpt: Optional[BaselineOption] = None
    barOpt: Optional[BarOption] = None
    hLineOpt: Optional[HorizontalLineOption] = None
    vLineOpt: Optional[VerticalLineOption] = None


@dataclass
class ChartConfig:
    """
    图表配置

    新架构说明：
    - chart 是一个三维数组
    - 第1维：时间周期（如 15m, 1h, 4h）
    - 第2维：面板（主图、副图1、副图2...）
    - 第3维：该面板内的所有系列配置
    """

    template: str
    chart: List[List[List[SeriesItemConfig]]]

    showBottomRow: bool = True
    viewMode: Literal["chart", "table"] = "chart"
    selectedInternalFileName: str = ""


# --- Overrides ---


class DashboardOverride(TypedDict, total=False):
    template: str
    showBottomRow: bool
    viewMode: Literal["chart", "table"]
    selectedInternalFileName: str
    selectedZipFileName: str  # Browser only
