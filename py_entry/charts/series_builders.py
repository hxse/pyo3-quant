"""
图表系列配置构建器

提供便捷函数用于创建各种图表系列配置，自动处理默认值和类型转换。
"""

from typing import Optional, Union
from py_entry.types import SeriesItemConfig
from .options import (
    CandleOption,
    LineOption,
    HistogramOption,
    AreaOption,
    BaselineOption,
    BarOption,
    HorizontalLineOption,
    VerticalLineOption,
)


def create_candle_series(
    file_name: str,
    show: bool = True,
    up_color: str = "#26a69a",
    down_color: str = "#ef5350",
    border_visible: bool = True,
    **kwargs,
) -> SeriesItemConfig:
    """
    创建蜡烛图系列配置

    Args:
        file_name: 数据文件路径
        show: 是否显示
        up_color: 上涨颜色
        down_color: 下跌颜色
        border_visible: 是否显示边框
        **kwargs: 其他 CandleOption 参数

    Returns:
        SeriesItemConfig 对象
    """
    candle_opt = CandleOption(
        upColor=up_color,
        downColor=down_color,
        borderVisible=border_visible,
        **kwargs,
    )

    return SeriesItemConfig(
        type="candle",
        fileName=file_name,
        dataName=["open", "high", "low", "close"],
        show=show,
        candleOpt=candle_opt,
    )


def create_line_series(
    file_name: str,
    data_name: str,
    show: bool = True,
    color: Optional[str] = None,
    line_width: int = 2,
    line_style: int = 0,
    **kwargs,
) -> SeriesItemConfig:
    """
    创建折线图系列配置

    Args:
        file_name: 数据文件路径
        data_name: 数据列名
        show: 是否显示
        color: 线条颜色（None 时使用默认值）
        line_width: 线条宽度
        line_style: 线条样式（0=实线, 1=点线, 2=虚线）
        **kwargs: 其他 LineOption 参数

    Returns:
        SeriesItemConfig 对象
    """
    line_opt = LineOption(
        color=color,
        lineWidth=line_width,
        lineStyle=line_style,
        **kwargs,
    )

    return SeriesItemConfig(
        type="line",
        fileName=file_name,
        dataName=data_name,
        show=show,
        lineOpt=line_opt,
    )


def create_histogram_series(
    file_name: str,
    data_name: str,
    show: bool = True,
    color: str = "#26a69a",
    base: float = 0,
) -> SeriesItemConfig:
    """
    创建直方图系列配置

    Args:
        file_name: 数据文件路径
        data_name: 数据列名
        show: 是否显示
        color: 柱子颜色
        base: 基线值

    Returns:
        SeriesItemConfig 对象
    """
    histogram_opt = HistogramOption(color=color, base=base)

    return SeriesItemConfig(
        type="histogram",
        fileName=file_name,
        dataName=data_name,
        show=show,
        histogramOpt=histogram_opt,
    )


def create_volume_series(
    file_name: str,
    show: bool = True,
    price_scale_margin_top: float = 0.7,
    adjust_main_series: bool = True,
) -> SeriesItemConfig:
    """
    创建成交量系列配置

    Args:
        file_name: 数据文件路径
        show: 是否显示
        price_scale_margin_top: 叠加层顶部边距(0-1)，默认 0.7 表示 volume 占据底部 30%
        adjust_main_series: 是否自动调整主系列避免重叠，默认 True

    Returns:
        SeriesItemConfig 对象
    """
    from .options import VolumeOption

    volume_opt = VolumeOption(
        priceScaleMarginTop=price_scale_margin_top,
        adjustMainSeries=adjust_main_series,
    )

    return SeriesItemConfig(
        type="volume",
        fileName=file_name,
        dataName="volume",
        show=show,
        volumeOpt=volume_opt,
    )


def create_area_series(
    file_name: str,
    data_name: str,
    show: bool = True,
    top_color: str = "rgba(41, 98, 255, 0.28)",
    bottom_color: str = "rgba(41, 98, 255, 0.05)",
    line_color: str = "#2962FF",
    line_width: int = 3,
    **kwargs,
) -> SeriesItemConfig:
    """
    创建面积图系列配置

    Args:
        file_name: 数据文件路径
        data_name: 数据列名
        show: 是否显示
        top_color: 面积顶部颜色
        bottom_color: 面积底部颜色
        line_color: 边线颜色
        line_width: 边线宽度
        **kwargs: 其他 AreaOption 参数

    Returns:
        SeriesItemConfig 对象
    """
    area_opt = AreaOption(
        topColor=top_color,
        bottomColor=bottom_color,
        lineColor=line_color,
        lineWidth=line_width,
        **kwargs,
    )

    return SeriesItemConfig(
        type="area",
        fileName=file_name,
        dataName=data_name,
        show=show,
        areaOpt=area_opt,
    )


def create_baseline_series(
    file_name: str,
    data_name: str,
    show: bool = True,
    base_value: float = 0,
    top_line_color: str = "#26a69a",
    bottom_line_color: str = "#ef5350",
    **kwargs,
) -> SeriesItemConfig:
    """
    创建基线图系列配置

    Args:
        file_name: 数据文件路径
        data_name: 数据列名
        show: 是否显示
        base_value: 基线值
        top_line_color: 基线上方线条颜色
        bottom_line_color: 基线下方线条颜色
        **kwargs: 其他 BaselineOption 参数

    Returns:
        SeriesItemConfig 对象
    """
    baseline_opt = BaselineOption(
        baseValue=base_value,
        topLineColor=top_line_color,
        bottomLineColor=bottom_line_color,
        **kwargs,
    )

    return SeriesItemConfig(
        type="baseline",
        fileName=file_name,
        dataName=data_name,
        show=show,
        baselineOpt=baseline_opt,
    )


def create_bar_series(
    file_name: str,
    show: bool = True,
    up_color: str = "#26a69a",
    down_color: str = "#ef5350",
    thin_bars: bool = False,
) -> SeriesItemConfig:
    """
    创建条形图系列配置

    Args:
        file_name: 数据文件路径
        show: 是否显示
        up_color: 上涨条形颜色
        down_color: 下跌条形颜色
        thin_bars: 是否使用细条形

    Returns:
        SeriesItemConfig 对象
    """
    bar_opt = BarOption(
        upColor=up_color,
        downColor=down_color,
        thinBars=thin_bars,
    )

    return SeriesItemConfig(
        type="bar",
        fileName=file_name,
        dataName=["open", "high", "low", "close"],
        show=show,
        barOpt=bar_opt,
    )


def create_hline(
    value: float,
    color: str,
    label: Optional[str] = None,
    show_label: bool = False,
    show: bool = True,
) -> SeriesItemConfig:
    """
    创建水平参考线配置

    Args:
        value: 水平线的价格值
        color: 线条颜色
        label: 标签文本
        show_label: 是否显示标签
        show: 是否显示

    Returns:
        SeriesItemConfig 对象
    """
    hline_opt = HorizontalLineOption(
        value=value, color=color, label=label, showLabel=show_label
    )

    return SeriesItemConfig(
        type="hline",
        show=show,
        hLineOpt=hline_opt,
    )


def create_vline(
    value: Union[int, float, str],
    color: str,
    label: Optional[str] = None,
    show_label: bool = False,
    show: bool = True,
) -> SeriesItemConfig:
    """
    创建垂直参考线配置

    Args:
        value: 时间值（Unix时间戳或日期字符串）
        color: 线条颜色
        label: 标签文本
        show_label: 是否显示标签
        show: 是否显示

    Returns:
        SeriesItemConfig 对象
    """
    vline_opt = VerticalLineOption(
        value=value, color=color, label=label, showLabel=show_label
    )

    return SeriesItemConfig(
        type="vline",
        show=show,
        vLineOpt=vline_opt,
    )
