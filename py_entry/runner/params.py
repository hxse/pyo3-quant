from pydantic import BaseModel, ConfigDict
from typing import TYPE_CHECKING, Optional, Union
from py_entry.types import (
    IndicatorsParams,
    SignalParams,
    BacktestParams,
    PerformanceParams,
    SignalTemplate,
    SettingContainer,
    ChartConfig,
)
from py_entry.data_generator import OtherParams, DataSourceConfig
from py_entry.io import ParquetCompression
from py_entry.charts.settings import IndicatorLayout


class SetupConfig(BaseModel):
    """setup() 方法配置"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    data_source: Optional[DataSourceConfig] = None
    other_params: Optional[OtherParams] = None
    indicators: Optional[IndicatorsParams] = None
    signal: Optional[SignalParams] = None
    backtest: Optional[BacktestParams] = None
    performance: Optional[PerformanceParams] = None
    signal_template: Optional[SignalTemplate] = None
    engine_settings: Optional[SettingContainer] = None
    param_set_size: int = 1
    enable_timing: bool = False


class FormatResultsConfig(BaseModel):
    """format_results_for_export() 方法配置"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    dataframe_format: str = "csv"
    compress_level: int = 1
    parquet_compression: ParquetCompression = "zstd"
    chart_config: Optional[ChartConfig] = None
    indicator_layout: Optional[IndicatorLayout] = None
    add_index: bool = True
    add_time: bool = True
    add_date: bool = True


class DiagnoseStatesConfig(BaseModel):
    """diagnose_states() 方法配置"""

    result_index: int = 0
    print_summary: bool = True
