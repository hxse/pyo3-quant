from typing import Optional

from py_entry.types import (
    BacktestSummary,
    DataContainer,
    HorizontalLineOption,
    SeriesItemConfig,
    SingleParamSet,
)

from .core_helpers import get_style_option, init_counter, match_indicator_columns
from .settings import IGNORE_COLS, IndicatorLayout
from .utils import sort_timeframe_keys


def build_chart_groups(
    data_dict: DataContainer,
    result: BacktestSummary,
    param: SingleParamSet,
    layout: IndicatorLayout,
    dataframe_format: str,
) -> list[list[list[SeriesItemConfig]]]:
    """构建主图 chart 三维结构（时间周期 > 面板 > 系列）。"""
    chart_groups: list[list[list[SeriesItemConfig]]] = []

    source_keys = set(data_dict.source.keys())
    ind_keys = set(result.indicators.keys()) if result.indicators else set()
    all_keys = source_keys | ind_keys

    if not data_dict.base_data_key:
        return chart_groups

    sorted_keys = sort_timeframe_keys(list(all_keys), data_dict.base_data_key)

    for key in sorted_keys:
        available_columns = set()
        if result.indicators and key in result.indicators:
            dataframe = result.indicators[key]
            available_columns = set(
                col for col in dataframe.columns if col not in IGNORE_COLS
            )

        tf_panels: list[list[SeriesItemConfig]] = []

        for panel_layout in layout:
            panel_series: list[SeriesItemConfig] = []
            style_counters: dict[str, int] = {}

            for item_config in panel_layout:
                indicator_name = item_config.indicator
                item_type = item_config.type
                show = item_config.show
                show_in_legend = item_config.showInLegend

                if indicator_name == "ohlc" and item_type == "candle":
                    if key in data_dict.source:
                        counter = init_counter(style_counters, indicator_name)
                        candle_opt = get_style_option(
                            item_config.candleOptions, counter
                        )
                        panel_series.append(
                            SeriesItemConfig(
                                type="candle",
                                fileName=f"data_dict/source_{key}.{dataframe_format}",
                                dataName=["open", "high", "low", "close"],
                                show=show,
                                showInLegend=show_in_legend,
                                candleOpt=candle_opt,
                            )
                        )
                        style_counters[indicator_name] += 1

                elif indicator_name == "volume" and item_type == "volume":
                    if key in data_dict.source:
                        counter = init_counter(style_counters, indicator_name)
                        volume_opt = get_style_option(
                            item_config.volumeOptions, counter
                        )
                        panel_series.append(
                            SeriesItemConfig(
                                type="volume",
                                fileName=f"data_dict/source_{key}.{dataframe_format}",
                                dataName="volume",
                                show=show,
                                showInLegend=show_in_legend,
                                volumeOpt=volume_opt,
                            )
                        )
                        style_counters[indicator_name] += 1

                elif item_type == "histogram":
                    matched_columns = match_indicator_columns(
                        indicator_name, available_columns
                    )
                    for matched_column in matched_columns:
                        counter = init_counter(style_counters, indicator_name)
                        histogram_opt = get_style_option(
                            item_config.histogramOptions,
                            counter,
                        )
                        panel_series.append(
                            SeriesItemConfig(
                                type="histogram",
                                fileName=f"backtest_results/indicators_{key}.{dataframe_format}",
                                dataName=matched_column,
                                show=show,
                                showInLegend=show_in_legend,
                                histogramOpt=histogram_opt,
                            )
                        )
                        style_counters[indicator_name] += 1

                elif item_type == "hline":
                    indicator_base = (
                        indicator_name.replace("_upper", "")
                        .replace("_center", "")
                        .replace("_lower", "")
                        .replace("_zero", "")
                    )
                    has_related_indicator = any(
                        col.startswith(indicator_base) for col in available_columns
                    )
                    if not has_related_indicator:
                        continue

                    hline_value: Optional[float] = item_config.value
                    if hline_value is None and param and param.signal:
                        param_name = indicator_name
                        if param_name in param.signal:
                            hline_value = float(param.signal[param_name].value)

                    if hline_value is not None:
                        if item_config.hLineOpt:
                            hline_opt = item_config.hLineOpt
                        else:
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
                                showLabel=item_config.showLabel,
                            )

                        panel_series.append(
                            SeriesItemConfig(
                                type="hline",
                                hLineOpt=hline_opt,
                                show=show,
                                showInLegend=show_in_legend,
                            )
                        )

                elif item_type == "vline":
                    if item_config.vLineOpt:
                        vline_opt = item_config.vLineOpt
                        panel_series.append(
                            SeriesItemConfig(
                                type="vline",
                                vLineOpt=vline_opt,
                                show=show,
                                showInLegend=show_in_legend,
                            )
                        )

                elif item_type == "line":
                    matched_columns = match_indicator_columns(
                        indicator_name, available_columns
                    )
                    for matched_column in matched_columns:
                        counter = init_counter(style_counters, indicator_name)
                        line_opt = get_style_option(item_config.lineOptions, counter)
                        panel_series.append(
                            SeriesItemConfig(
                                type="line",
                                fileName=f"backtest_results/indicators_{key}.{dataframe_format}",
                                dataName=matched_column,
                                show=show,
                                showInLegend=show_in_legend,
                                lineOpt=line_opt,
                            )
                        )
                        style_counters[indicator_name] += 1

            if panel_series:
                tf_panels.append(panel_series)

        if tf_panels:
            chart_groups.append(tf_panels)

    return chart_groups
