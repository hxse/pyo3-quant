from typing import TYPE_CHECKING
from py_entry.types import ChartConfig
from py_entry.charts.generation import (
    generate_default_chart_config,
)

if TYPE_CHECKING:
    from .runner import BacktestRunner


def generate_chart_config(
    self: "BacktestRunner",
    custom_config: ChartConfig | None = None,
    dataframe_format: str = "csv",
) -> None:
    """
    生成或设置 ChartConfigJSON。

    注意：应该先调用 format_results_for_export() 选择 result 和 param。
    """
    if custom_config:
        self.chart_config = custom_config
    elif (
        self.data_dict
        and self.results
        and self.param_set
        and self.export_index is not None
    ):
        selected_result = self.results[self.export_index]
        selected_param = self.param_set[self.export_index]

        # 注意：generate_default_chart_config 的签名将在后续步骤更新
        self.chart_config = generate_default_chart_config(
            self.data_dict, selected_result, selected_param, dataframe_format
        )
    else:
        # 改为直接报错
        raise ValueError(
            "无法生成 ChartConfig: 缺少数据或未选择回测结果。"
            "请先调用 format_results_for_export(export_index=N)。"
        )
