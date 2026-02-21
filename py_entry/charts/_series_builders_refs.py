"""参考线系列配置构建函数。"""

from typing import Literal, Optional, Union

from py_entry.types import SeriesItemConfig

from .options import HorizontalLineOption, VerticalLineOption


def create_hline(
    value: float,
    color: str,
    label: Optional[str] = None,
    show_label: bool = False,
    line_width: Optional[Literal[1, 2, 3, 4]] = None,
    line_style: Optional[Literal[0, 1, 2, 3, 4]] = None,
    line_visible: Optional[bool] = None,
    axis_label_visible: Optional[bool] = None,
    axis_label_color: Optional[str] = None,
    axis_label_text_color: Optional[str] = None,
    show: bool = True,
) -> SeriesItemConfig:
    """创建水平参考线配置。"""
    hline_opt = HorizontalLineOption(
        value=value,
        color=color,
        label=label,
        showLabel=show_label,
        lineWidth=line_width,  # 中文注释：可选透传线宽。
        lineStyle=line_style,  # 中文注释：可选透传线型。
        lineVisible=line_visible,
        axisLabelVisible=axis_label_visible,
        axisLabelColor=axis_label_color,
        axisLabelTextColor=axis_label_text_color,
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
    shape: Optional[Literal["arrowUp", "arrowDown", "circle", "square"]] = None,
    size: Optional[int] = None,
    position: Optional[Literal["aboveBar", "belowBar", "inBar"]] = None,
    show: bool = True,
) -> SeriesItemConfig:
    """创建垂直参考线配置。"""
    vline_opt = VerticalLineOption(
        value=value,
        color=color,
        label=label,
        showLabel=show_label,
        shape=shape,  # 中文注释：可选透传 marker 形状。
        size=size,
        position=position,
    )

    return SeriesItemConfig(
        type="vline",
        show=show,
        vLineOpt=vline_opt,
    )
