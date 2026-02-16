"""参考线系列配置构建函数。"""

from typing import Optional, Union

from py_entry.types import SeriesItemConfig

from .options import HorizontalLineOption, VerticalLineOption


def create_hline(
    value: float,
    color: str,
    label: Optional[str] = None,
    show_label: bool = False,
    show: bool = True,
) -> SeriesItemConfig:
    """创建水平参考线配置。"""
    hline_opt = HorizontalLineOption(
        value=value,
        color=color,
        label=label,
        showLabel=show_label,
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
    """创建垂直参考线配置。"""
    vline_opt = VerticalLineOption(
        value=value,
        color=color,
        label=label,
        showLabel=show_label,
    )

    return SeriesItemConfig(
        type="vline",
        show=show,
        vLineOpt=vline_opt,
    )
