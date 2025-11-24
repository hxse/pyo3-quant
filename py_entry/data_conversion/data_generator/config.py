"""
数据生成器配置类
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from py_entry.data_conversion.file_utils.types import RequestConfig


@dataclass
class DataGenerationParams:
    """数据生成参数配置类"""

    timeframes: list[str]
    start_time: int | None = None
    num_bars: int = 1000
    fixed_seed: bool = False


@dataclass
class OtherParams:
    """其他参数配置类，用于存放不太重要的参数"""

    brick_size: float = 2.0
    ha_enable: bool = True
    renko_enable: bool = True


@dataclass
class OhlcvDataFetchConfig:
    """OHLCV数据获取配置类"""

    config: "RequestConfig"  # 使用字符串避免循环导入
    timeframes: list[str]
    start_time: int
    count: int = 10
    enable_cache: bool = True
