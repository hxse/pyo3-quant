import time
from typing import TYPE_CHECKING
from loguru import logger

if TYPE_CHECKING:
    from .runner import BacktestRunner

from py_entry.io import (
    SaveConfig,
    UploadConfig,
    convert_backtest_data_to_buffers,
    save_backtest_results,
    upload_backtest_results,
    ParquetCompression,
)
from py_entry.io.dataframe_utils import (
    add_contextual_columns_to_dataframes,
)
from py_entry.io.zip_utils import create_zip_buffer
from py_entry.types import ChartConfig
from py_entry.charts.generation import (
    generate_default_chart_config,
)
from py_entry.charts.settings import IndicatorLayout
from typing import Optional


def format_results_for_export(
    self: "BacktestRunner",
    export_index: int,
    dataframe_format: str = "csv",
    compress_level: int = 1,
    parquet_compression: ParquetCompression = "snappy",
    chart_config: Optional[ChartConfig] = None,
    indicator_layout: Optional[IndicatorLayout] = None,
    add_index: bool = True,
    add_time: bool = True,
    add_date: bool = True,
) -> None:
    """
    为导出准备单个回测结果的数据。

    这个方法执行以下操作：
    1. 验证并选择要导出的 result 和 param
    2. 为选中的 DataFrame 添加上下文列（索引、时间、日期）
    3. 生成或设置图表配置 (ChartConfig)
    4. 将选中的数据转换为文件 Buffers
    5. 生成 ZIP 压缩包数据

    结果存储在实例属性 `export_buffers` 和 `export_zip_buffer` 中。

    Args:
        export_index: 要导出的结果索引（同时用于 results 和 param_set）
    """
    start_time = time.perf_counter() if self.enable_timing else None

    # 1. 验证 results 和 param_set 不为空
    if not self.results:
        raise ValueError("无回测结果可供导出。请先调用 run() 执行回测。")

    if not self.param_set:
        raise ValueError("无参数集可供导出。请先调用 run() 执行回测。")

    # 2. 验证 export_index 有效性（同时验证 results 和 param_set）
    if export_index < 0 or export_index >= len(self.results):
        raise IndexError(
            f"export_index {export_index} 超出 results 范围。"
            f"有效范围: 0 到 {len(self.results) - 1}"
        )

    if export_index >= len(self.param_set):
        raise IndexError(
            f"export_index {export_index} 超出 param_set 范围。"
            f"有效范围: 0 到 {len(self.param_set) - 1}"
        )

    # 3. 存储选中的索引
    self.export_index = export_index

    # 4. 获取单个对象
    selected_result = self.results[export_index]
    selected_param = self.param_set[export_index]

    # 5. 为 DataFrame 添加上下文列（传入单个 result）
    add_contextual_columns_to_dataframes(
        self.data_dict, selected_result, add_index, add_time, add_date
    )

    # 6. ChartConfig - 三级优先级
    # 1) 如果传入了 chart_config，直接使用
    # 2) 如果传入了 indicator_layout，使用它生成 chart_config
    # 3) 否则使用默认的 INDICATOR_LAYOUT 生成 chart_config
    if chart_config is not None:
        self.chart_config = chart_config
    elif indicator_layout is not None:
        if self.data_dict:
            self.chart_config = generate_default_chart_config(
                self.data_dict,
                selected_result,
                selected_param,
                dataframe_format,
                indicator_layout,
            )
    else:
        if self.data_dict:
            self.chart_config = generate_default_chart_config(
                self.data_dict, selected_result, selected_param, dataframe_format
            )

    # 7. Convert to buffers
    self.export_buffers = convert_backtest_data_to_buffers(
        self.data_dict,
        selected_param,
        self.template_config,
        self.engine_settings,
        selected_result,
        dataframe_format,
        parquet_compression,
        self.chart_config,
    )

    # 8. Generate ZIP
    if self.export_buffers:
        self.export_zip_buffer = create_zip_buffer(
            self.export_buffers, compress_level=compress_level
        )

    if self.enable_timing and start_time is not None:
        elapsed = time.perf_counter() - start_time
        logger.info(f"BacktestRunner.format_results_for_export() 耗时: {elapsed:.4f}秒")


def save_results(self: "BacktestRunner", config: SaveConfig) -> None:
    """
    保存所有回测数据（包括配置和结果）到本地文件。

    Args:
        self: BacktestRunner 实例。
        config: 保存配置对象
    """
    start_time = time.perf_counter() if self.enable_timing else None

    if self.export_buffers is None:
        raise ValueError(
            "未找到导出数据缓存。请先调用 format_results_for_export() 生成数据。"
        )

    # 调用工具函数保存结果
    save_backtest_results(
        buffers=self.export_buffers,
        config=config,
    )

    if self.enable_timing and start_time is not None:
        elapsed = time.perf_counter() - start_time
        logger.info(f"BacktestRunner.save_results() 耗时: {elapsed:.4f}秒")


def upload_results(self: "BacktestRunner", config: UploadConfig) -> None:
    """
    将所有回测数据（包括配置和结果）打包并上传到服务器。

    Args:
        self: BacktestRunner 实例。
        config: 上传配置对象
    """
    start_time = time.perf_counter() if self.enable_timing else None

    if self.export_zip_buffer is None:
        raise ValueError(
            "未找到导出的ZIP数据。请先调用 format_results_for_export() 生成数据。"
        )

    upload_backtest_results(
        zip_data=self.export_zip_buffer,
        config=config,
    )

    if self.enable_timing and start_time is not None:
        elapsed = time.perf_counter() - start_time
        logger.info(f"BacktestRunner.upload_results() 耗时: {elapsed:.4f}秒")
