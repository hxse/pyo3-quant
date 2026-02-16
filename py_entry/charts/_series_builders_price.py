"""价格相关图表系列配置构建函数。"""

from typing import Optional

from py_entry.types import SeriesItemConfig

from .options import (
    AreaOption,
    BarOption,
    BaselineOption,
    CandleOption,
    HistogramOption,
    LineOption,
    VolumeOption,
)


def create_candle_series(
    file_name: str,
    show: bool = True,
    up_color: str = "#26a69a",
    down_color: str = "#ef5350",
    border_visible: bool = True,
    **kwargs,
) -> SeriesItemConfig:
    """创建蜡烛图系列配置。"""
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
    """创建折线图系列配置。"""
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
    """创建直方图系列配置。"""
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
    """创建成交量系列配置。"""
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
    """创建面积图系列配置。"""
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
    """创建基线图系列配置。"""
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
    """创建条形图系列配置。"""
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
