"""
数据生成器配置类
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict
import polars as pl

from py_entry.data_conversion.file_utils.types import RequestConfig


@dataclass
class DataGenerationParams:
    """数据生成参数配置类"""

    timeframes: list[str]
    start_time: int | None
    num_bars: int
    fixed_seed: bool
    BaseDataKey: str


@dataclass
class OhlcvDataFetchConfig:
    """OHLCV数据获取配置类"""

    config: RequestConfig
    timeframes: list[str]
    start_time: int
    count: int
    enable_cache: bool
    BaseDataKey: str


@dataclass
class OtherParams:
    """其他参数配置类，用于存放不太重要的参数"""

    brick_size: float = 2.0
    ha_timeframes: list[str] | None = None
    renko_timeframes: list[str] | None = None


@dataclass
class DirectDataConfig:
    """直接数据配置类"""

    data: Dict[str, pl.DataFrame]
    BaseDataKey: str
