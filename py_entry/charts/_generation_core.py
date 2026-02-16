from typing import Optional

from py_entry.types import (
    BacktestSummary,
    ChartConfig,
    DataContainer,
    SingleParamSet,
)

from ._generation_bottom import build_bottom_row_chart
from ._generation_panels import build_chart_groups
from ._generation_template import choose_template
from .settings import INDICATOR_LAYOUT, IndicatorLayout


def generate_default_chart_config(
    data_dict: DataContainer,
    result: BacktestSummary,
    param: SingleParamSet,
    dataframe_format: str = "csv",
    indicator_layout: Optional[IndicatorLayout] = None,
) -> ChartConfig:
    """根据回测数据和布局配置生成图表配置。"""
    layout = indicator_layout if indicator_layout is not None else INDICATOR_LAYOUT
    if not data_dict.base_data_key:
        return ChartConfig(template="single", chart=[])

    chart_groups = build_chart_groups(
        data_dict=data_dict,
        result=result,
        param=param,
        layout=layout,
        dataframe_format=dataframe_format,
    )

    template = choose_template(len(chart_groups)) if chart_groups else "single"
    bottom_row_chart = build_bottom_row_chart(result, dataframe_format)

    selected_file_name = (
        f"data_dict/source_{data_dict.base_data_key}.{dataframe_format}"
    )

    return ChartConfig(
        template=template,
        chart=chart_groups,
        bottomRowChart=bottom_row_chart if bottom_row_chart else None,
        selectedInternalFileName=selected_file_name,
        showBottomRow=True,
        showLegendInAll=True,
    )
