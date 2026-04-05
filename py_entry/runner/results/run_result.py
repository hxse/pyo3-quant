import time
from typing import TYPE_CHECKING, Any, List, Tuple, Self, Union, cast
from io import BytesIO
from pathlib import Path
from loguru import logger
import polars as pl

from py_entry.types import (
    BacktestParamSegment,
    ResultPack,
    SingleParamSet,
    DataPack,
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
from py_entry.runner.results.report_json import dump_report

# Avoid circular imports for type checking if needed, though mostly using imported types
if TYPE_CHECKING:
    from py_entry.runner.display.chart_widget import ChartDashboardWidget
    from IPython.display import HTML
    from marimo._plugins.ui._impl.from_anywidget import anywidget as MarimoAnyWidget

# Lazy import display to avoid circular dependency if possible, or import at top if safe.
# Assuming display doesn't import run_result.
from py_entry.runner import display as _display

_USE_DEFAULT_EXPORT_PARAMS = object()


def _clone_optional_df(df: pl.DataFrame | None) -> pl.DataFrame | None:
    """克隆可选 DataFrame。"""
    if df is None:
        return None
    return df.clone()


def _copy_data_pack(pack: DataPack) -> DataPack:
    """深拷贝 DataPack，避免导出逻辑污染计算态对象。"""
    ranges = {k: v for k, v in pack.ranges.items()}
    mapping = _clone_optional_df(pack.mapping)
    if mapping is None:
        mapping = pl.DataFrame()
    skip_mask = _clone_optional_df(pack.skip_mask)
    source = {k: v.clone() for k, v in pack.source.items()}
    return DataPack(
        mapping=mapping,
        skip_mask=skip_mask,
        source=source,
        base_data_key=pack.base_data_key,
        ranges=ranges,
    )


def _copy_result_pack(result: ResultPack) -> ResultPack:
    """深拷贝 ResultPack，确保 format_for_export 不改原始结果。"""
    indicators = None
    if result.indicators is not None:
        indicators = {k: v.clone() for k, v in result.indicators.items()}
    signals = _clone_optional_df(result.signals)
    backtest_result = _clone_optional_df(result.backtest_result)
    performance = dict(result.performance) if result.performance is not None else None
    ranges = {k: v for k, v in result.ranges.items()}
    mapping = _clone_optional_df(result.mapping)
    if mapping is None:
        mapping = pl.DataFrame()
    return ResultPack(
        mapping=mapping,
        ranges=ranges,
        base_data_key=result.base_data_key,
        performance=performance,
        indicators=indicators,
        signals=signals,
        backtest_result=backtest_result,
    )


class RunResult:
    """单个回测结果，包含所有工具方法"""

    def __init__(
        self,
        result: ResultPack,
        params: SingleParamSet,
        data_pack: DataPack,
        template_config: TemplateContainer,
        engine_settings: SettingContainer,
        enable_timing: bool = False,
        export_params: SingleParamSet | None | object = _USE_DEFAULT_EXPORT_PARAMS,
        backtest_schedule: list[BacktestParamSegment] | None = None,
    ):
        self.result = result
        self.params = params
        self.data_pack = data_pack
        self.template_config = template_config
        self.engine_settings = engine_settings
        self.enable_timing = enable_timing
        # 中文注释：默认沿用单次回测 params；WF stitched 可显式传 None，表示导出时不再伪造单一参数集。
        if export_params is _USE_DEFAULT_EXPORT_PARAMS:
            resolved_export_params: SingleParamSet | None = params
        else:
            resolved_export_params = cast(SingleParamSet | None, export_params)
        self.export_params: SingleParamSet | None = resolved_export_params
        self.backtest_schedule = backtest_schedule

        # 导出缓存
        self._export_buffers: List[Tuple[Path, BytesIO]] | None = None
        self._export_zip_buffer: bytes | None = None
        self._chart_config: ChartConfig | None = None

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

        # 1. 导出链路在副本上处理，避免污染计算态 data_pack/result。
        export_data = _copy_data_pack(self.data_pack)
        export_result = _copy_result_pack(self.result)

        # 2. 为导出副本添加上下文列
        add_contextual_columns_to_dataframes(
            export_data,
            export_result,
            config.add_index,
            config.add_time,
            config.add_date,
        )

        # 3. ChartConfig
        if config.chart_config is not None:
            self._chart_config = config.chart_config
        else:
            # 中文注释：仅使用调用方显式传入布局；未传时由图表层使用全局默认布局。
            indicator_layout = config.indicator_layout
            chart_params = None if self.backtest_schedule is not None else self.params
            if export_data:
                self._chart_config = generate_default_chart_config(
                    export_data,
                    export_result,
                    chart_params,
                    config.dataframe_format,
                    indicator_layout,
                )

        # 4. Convert to buffers
        self._export_buffers = convert_backtest_data_to_buffers(
            export_data,
            self.export_params,
            self.template_config,
            self.engine_settings,
            export_result,
            config.dataframe_format,
            config.parquet_compression,
            self._chart_config,
            self.backtest_schedule,
        )

        # 5. Generate ZIP
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
    ) -> Union["HTML", "ChartDashboardWidget", "MarimoAnyWidget"]:
        """显示图表"""
        # 中文注释：展示层直接消费正式字段 result / params / data_pack / chart_config。
        return _display.display_dashboard(self, config)

    def build_report(self) -> dict[str, Any]:
        """构建统一回测报告。"""
        perf = self.result.performance or {}
        # 中文注释：日志输出仅保留单一结构，不再区分 brief/detailed。
        return {
            "stage": "backtest",
            "performance": perf,
        }

    def print_report(self) -> None:
        """打印统一回测报告。"""
        print(dump_report(self.build_report()))
