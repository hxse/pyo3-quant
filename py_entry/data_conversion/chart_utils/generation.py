from typing import List, Optional

from py_entry.data_conversion.types import (
    DataContainer,
    SingleParamSet,
    BacktestSummary,
)
from py_entry.data_conversion.types.chart_config import (
    ChartConfig,
    SeriesItemConfig,
    HorizontalLineOption,
)

from .settings import IGNORE_COLS, INDICATOR_LAYOUT, IndicatorLayout
from .utils import sort_timeframe_keys
from .core_helpers import (
    get_style_option,
    init_counter,
    match_indicator_columns,
)


def generate_default_chart_config(
    data_dict: DataContainer,
    result: BacktestSummary,
    param: SingleParamSet,
    dataframe_format: str = "csv",
    indicator_layout: Optional[IndicatorLayout] = None,
) -> ChartConfig:
    """
    根据单个回测数据和 INDICATOR_LAYOUT 生成图表配置。

    Args:
        data_dict: 数据容器
        result: 单个回测结果
        param: 单个参数集
        dataframe_format: 数据格式 ("csv" 或 "parquet")
        indicator_layout: 可选的指标布局配置,如果为 None 则使用默认的 INDICATOR_LAYOUT

    Returns:
        ChartConfig 对象（3维数组：时间周期 > 面板 > 系列）
    """

    # 使用传入的 indicator_layout 或默认的 INDICATOR_LAYOUT
    layout = indicator_layout if indicator_layout is not None else INDICATOR_LAYOUT

    chart_groups: List[List[List[SeriesItemConfig]]] = []

    # 收集所有的数据源键
    source_keys = set(data_dict.source.keys())
    ind_keys = set()
    if result.indicators:
        ind_keys = set(result.indicators.keys())

    all_keys = source_keys | ind_keys

    # 排序时间周期
    if not data_dict.BaseDataKey:
        return ChartConfig(template="single", chart=chart_groups)

    sorted_keys = sort_timeframe_keys(list(all_keys), data_dict.BaseDataKey)

    # 为每个时间周期生成配置
    for key in sorted_keys:
        # 获取当前时间周期的指标数据列
        available_columns = set()
        if result.indicators and key in result.indicators:
            df = result.indicators[key]
            available_columns = set(c for c in df.columns if c not in IGNORE_COLS)

        # 当前时间周期的所有面板配置（3维：时间周期 > 面板 > 系列）
        tf_panels: List[List[SeriesItemConfig]] = []

        # 遍历 layout，为每个面板生成配置
        for panel_layout in layout:
            # 当前面板的系列配置
            panel_series: List[SeriesItemConfig] = []

            # 样式分配计数器（每个指标名在当前窗格内的计数）
            style_counters: dict[str, int] = {}

            for item_config in panel_layout:
                indicator_name = item_config.indicator
                item_type = item_config.type
                show = item_config.show

                # 处理不同类型的指标
                if indicator_name == "ohlc" and item_type == "candle":
                    # OHLC K线图
                    if key in data_dict.source:
                        # 获取当前指标在当前窗格的计数
                        counter = init_counter(style_counters, indicator_name)

                        # 获取 candle 样式选项（如果有配置）
                        candleOpt = get_style_option(item_config.candleOptions, counter)

                        panel_series.append(
                            SeriesItemConfig(
                                type="candle",
                                fileName=f"data_dict/source_{key}.{dataframe_format}",
                                dataName=["open", "high", "low", "close"],
                                show=show,
                                candleOpt=candleOpt,
                            )
                        )

                        style_counters[indicator_name] += 1

                elif indicator_name == "volume" and item_type == "volume":
                    # 成交量（使用独立的 volume 类型）
                    # 前端会自动处理涨跌颜色和叠加层配置
                    if key in data_dict.source:
                        # 获取当前指标在当前窗格的计数
                        counter = init_counter(style_counters, indicator_name)

                        # 获取 volume 样式选项（如果有配置）
                        volumeOpt = get_style_option(item_config.volumeOptions, counter)

                        panel_series.append(
                            SeriesItemConfig(
                                type="volume",
                                fileName=f"data_dict/source_{key}.{dataframe_format}",
                                dataName="volume",
                                show=show,
                                volumeOpt=volumeOpt,
                            )
                        )

                        style_counters[indicator_name] += 1

                elif item_type == "histogram":
                    # 普通直方图（非成交量）
                    # 查找匹配的列
                    matched_columns = match_indicator_columns(
                        indicator_name, available_columns
                    )

                    for matched_column in matched_columns:
                        # 获取当前指标在当前窗格的计数
                        counter = init_counter(style_counters, indicator_name)

                        # 获取 histogram 样式选项（如果有配置）
                        histogramOpt = get_style_option(
                            item_config.histogramOptions, counter
                        )

                        panel_series.append(
                            SeriesItemConfig(
                                type="histogram",
                                fileName=f"backtest_results/indicators_{key}.{dataframe_format}",
                                dataName=matched_column,
                                show=show,
                                histogramOpt=histogramOpt,
                            )
                        )

                        style_counters[indicator_name] += 1

                elif item_type == "hline":
                    # 水平线 - 只有当对应的指标存在时才添加
                    # 检查是否有相关的指标列存在
                    indicator_base = (
                        indicator_name.replace("_upper", "")
                        .replace("_center", "")
                        .replace("_lower", "")
                        .replace("_zero", "")
                    )

                    # 检查是否有匹配的指标
                    has_related_indicator = any(
                        col.startswith(indicator_base) for col in available_columns
                    )

                    if not has_related_indicator:
                        continue  # 跳过这个水平线

                    hline_value: Optional[float] = item_config.value

                    # 如果没有直接提供值，尝试从 param.signal 中获取
                    if hline_value is None and param and param.signal:
                        param_name = indicator_name
                        if param_name in param.signal:
                            hline_value = float(param.signal[param_name].value)

                    if hline_value is not None:
                        # 使用配置中的 hLineOpt，或推断颜色
                        if item_config.hLineOpt:
                            hline_opt = item_config.hLineOpt
                        else:
                            # 颜色推断
                            color = "#ffffff"
                            if "upper" in indicator_name:
                                color = "#ff4d4f"
                            elif "lower" in indicator_name:
                                color = "#52c41a"
                            elif "center" in indicator_name:
                                color = "#faad14"
                            elif "zero" in indicator_name:
                                color = "#808080"
                            hline_opt = HorizontalLineOption(
                                value=hline_value,
                                color=color,
                                label=indicator_name,
                            )

                        panel_series.append(
                            SeriesItemConfig(
                                type="hline",
                                hLineOpt=hline_opt,
                                show=show,
                            )
                        )

                elif item_type == "line":
                    # 普通指标线 - 可能匹配多个列（如多个 sma）
                    # 查找所有匹配的列
                    matched_columns = match_indicator_columns(
                        indicator_name, available_columns
                    )

                    for idx, matched_column in enumerate(matched_columns):
                        # 获取当前指标在当前窗格的计数
                        counter = init_counter(style_counters, indicator_name)

                        # 获取样式选项
                        lineOpt = get_style_option(item_config.lineOptions, counter)

                        panel_series.append(
                            SeriesItemConfig(
                                type="line",
                                fileName=f"backtest_results/indicators_{key}.{dataframe_format}",
                                dataName=matched_column,
                                show=show,
                                lineOpt=lineOpt,
                            )
                        )

                        style_counters[indicator_name] += 1

            # 如果当前面板有内容，添加到时间周期的面板列表
            if panel_series:
                tf_panels.append(panel_series)

        # 如果当前时间周期有面板，添加到总配置
        if tf_panels:
            chart_groups.append(tf_panels)

    # 根据图表数量自动调整模板
    # 文档支持的模板：
    # - single: 1个slot
    # - vertical-1x1, horizontal-1x1: 2个slot
    # - vertical-1x2, horizontal-1x2, vertical-1x1x1, horizontal-1x1x1: 3个slot
    # - grid-2x2: 4个slot
    template = "single"
    if len(chart_groups) == 1:
        template = "single"
    elif len(chart_groups) == 2:
        template = "horizontal-1x1"  # 水平2图
    elif len(chart_groups) == 3:
        template = "vertical-1x2"  # 垂直1大2小
    elif len(chart_groups) == 4:
        template = "grid-2x2"  # 2x2网格
    else:
        # 超过4个图表，默认使用 grid-2x2
        template = "grid-2x2"

    return ChartConfig(
        template=template,
        chart=chart_groups,
        selectedInternalFileName=f"data_dict/source_{data_dict.BaseDataKey}.{dataframe_format}",
        showBottomRow=True,
    )
