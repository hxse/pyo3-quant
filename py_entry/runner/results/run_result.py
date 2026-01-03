import time
from typing import TYPE_CHECKING, List, Tuple, Self, Optional, Union
from io import BytesIO
from pathlib import Path
from loguru import logger

from py_entry.types import (
    BacktestSummary,
    SingleParamSet,
    DataContainer,
    TemplateContainer,
    SettingContainer,
    ChartConfig,
)
from py_entry.io import (
    SaveConfig,
    UploadConfig,
    DisplayConfig,
    convert_backtest_data_to_buffers,
    save_backtest_results,
    upload_backtest_results,
)
from py_entry.io.dataframe_utils import add_contextual_columns_to_dataframes
from py_entry.io.zip_utils import create_zip_buffer
from py_entry.charts.generation import generate_default_chart_config
from py_entry.runner.params import FormatResultsConfig

# Avoid circular imports for type checking if needed, though mostly using imported types
if TYPE_CHECKING:
    from py_entry.runner.display.chart_widget import ChartDashboardWidget
    from IPython.display import HTML

# Lazy import display to avoid circular dependency if possible, or import at top if safe.
# Assuming display doesn't import run_result.
from py_entry.runner import display as _display


class RunResult:
    """单个回测结果，包含所有工具方法"""

    def __init__(
        self,
        summary: BacktestSummary,
        params: SingleParamSet,
        data_dict: DataContainer,
        template_config: TemplateContainer,
        engine_settings: SettingContainer,
        enable_timing: bool = False,
    ):
        self.summary = summary
        self.params = params
        self.data_dict = data_dict
        self.template_config = template_config
        self.engine_settings = engine_settings
        self.enable_timing = enable_timing

        # 导出缓存
        self._export_buffers: List[Tuple[Path, BytesIO]] | None = None
        self._export_zip_buffer: bytes | None = None
        self._chart_config: ChartConfig | None = None

    @property
    def results(self) -> List[BacktestSummary]:
        """兼容属性：返回单元素列表"""
        return [self.summary]

    @property
    def param_set(self) -> List[SingleParamSet]:
        """兼容属性：返回单元素列表"""
        return [self.params]

    @property
    def export_buffers(self):
        return self._export_buffers

    @property
    def export_zip_buffer(self):
        return self._export_zip_buffer

    @property
    def chart_config(self):
        return self._chart_config

    def format_for_export(self, config: FormatResultsConfig) -> Self:
        """为导出准备数据"""
        start_time = time.perf_counter() if self.enable_timing else None

        # 1. 为 DataFrame 添加上下文列
        add_contextual_columns_to_dataframes(
            self.data_dict,
            self.summary,
            config.add_index,
            config.add_time,
            config.add_date,
        )

        # 2. ChartConfig
        if config.chart_config is not None:
            self._chart_config = config.chart_config
        elif config.indicator_layout is not None:
            if self.data_dict:
                self._chart_config = generate_default_chart_config(
                    self.data_dict,
                    self.summary,
                    self.params,
                    config.dataframe_format,
                    config.indicator_layout,
                )
        else:
            if self.data_dict:
                self._chart_config = generate_default_chart_config(
                    self.data_dict,
                    self.summary,
                    self.params,
                    config.dataframe_format,
                )

        # 3. Convert to buffers
        self._export_buffers = convert_backtest_data_to_buffers(
            self.data_dict,
            self.params,
            self.template_config,
            self.engine_settings,
            self.summary,
            config.dataframe_format,
            config.parquet_compression,
            self._chart_config,
        )

        # 4. Generate ZIP
        if self._export_buffers:
            self._export_zip_buffer = create_zip_buffer(
                self._export_buffers, compress_level=config.compress_level
            )

        if self.enable_timing and start_time is not None:
            elapsed = time.perf_counter() - start_time
            logger.info(f"RunResult.format_for_export() 耗时: {elapsed:.4f}秒")

        return self

    def save(self, config: SaveConfig) -> Self:
        """保存到本地"""
        start_time = time.perf_counter() if self.enable_timing else None

        if self._export_buffers is None:
            raise ValueError(
                "未找到导出数据缓存。请先调用 format_for_export() 生成数据。"
            )

        save_backtest_results(
            buffers=self._export_buffers,
            config=config,
        )

        if self.enable_timing and start_time is not None:
            elapsed = time.perf_counter() - start_time
            logger.info(f"RunResult.save() 耗时: {elapsed:.4f}秒")

        return self

    def upload(self, config: UploadConfig) -> Self:
        """上传到服务器"""
        start_time = time.perf_counter() if self.enable_timing else None

        if self._export_zip_buffer is None:
            raise ValueError(
                "未找到导出的ZIP数据。请先调用 format_for_export() 生成数据。"
            )

        upload_backtest_results(
            zip_data=self._export_zip_buffer,
            config=config,
        )

        if self.enable_timing and start_time is not None:
            elapsed = time.perf_counter() - start_time
            logger.info(f"RunResult.upload() 耗时: {elapsed:.4f}秒")

        return self

    def display(
        self, config: DisplayConfig | None = None
    ) -> Union["HTML", "ChartDashboardWidget"]:
        """显示图表"""
        # Create a temporary runner-like object or modify display_dashboard to accept RunResult
        # Since _display.display_dashboard expects a runner, we can pass self if we duck-type enough attributes.
        # RunResult has .data_dict, .results, .param_set (properties), .chart_config
        # display_dashboard uses runner.results[0], runner.param_set[0], runner.data_dict, runner.chart_config
        # So RunResult should work if we mock the list attributes.

        # However, _display.display_dashboard implementation:
        # It calls render_as_html or render_as_widget.
        # These renderers likely use runner.data_dict, runner.results, etc.
        # Let's verify what display_dashboard needs.
        # But to be safe and clean, we should probably refactor display or make RunResult compatible.
        # I added properties .results and .param_set to mimic BacktestRunner.

        return _display.display_dashboard(self, config)  # type: ignore
