from py_entry.types import BacktestSummary, SeriesItemConfig

from .core_helpers import get_style_option
from .settings import BOTTOM_PANEL_LAYOUT


def build_bottom_row_chart(
    result: BacktestSummary,
    dataframe_format: str,
) -> list[list[list[SeriesItemConfig]]]:
    """构建底栏图表结构（Slot > Pane > Series）。"""
    bottom_row_chart: list[list[list[SeriesItemConfig]]] = []

    if result.backtest_result is None:
        return bottom_row_chart

    for slot_layout in BOTTOM_PANEL_LAYOUT:
        bottom_slot: list[list[SeriesItemConfig]] = []
        for pane_layout in slot_layout:
            bottom_panel: list[SeriesItemConfig] = []
            for item in pane_layout:
                line_opt = get_style_option(item.lineOptions, 0)
                bottom_panel.append(
                    SeriesItemConfig(
                        type=item.type,
                        show=item.show,
                        showInLegend=item.showInLegend,
                        fileName=f"backtest_results/backtest_result.{dataframe_format}",
                        dataName=item.indicator,
                        lineOpt=line_opt,
                    )
                )
            bottom_slot.append(bottom_panel)
        bottom_row_chart.append(bottom_slot)

    return bottom_row_chart
