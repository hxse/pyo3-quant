"""
数据生成器配置类
"""

from typing import Dict, Optional
from pydantic import BaseModel, ConfigDict
import polars as pl
from py_entry.io.types import RequestConfig


class DataGenerationParams(BaseModel):
    """数据生成参数配置类"""

    timeframes: list[str]
    start_time: int | None
    num_bars: int
    base_data_key: str
    fixed_seed: Optional[int] = None

    # 波动性参数
    volatility: float = 0.02
    # 趋势参数 (每 bar 的期望收益率偏移)
    trend: float = 0.0
    # 跳空因子
    gap_factor: float = 0.5
    # 极端行情概率
    extreme_prob: float = 0.0
    # 极端行情波动倍数
    extreme_mult: float = 3.0
    # 是否允许跳空 (默认 True, 设为 False 则 Open[i] == Close[i-1])
    allow_gaps: bool = True

    model_config = ConfigDict(arbitrary_types_allowed=True)


class OhlcvDataFetchConfig(BaseModel):
    """OHLCV数据获取配置类"""

    config: RequestConfig
    timeframes: list[str]
    start_time: int
    count: int
    enable_cache: bool
    base_data_key: str


class DirectDataConfig(BaseModel):
    """直接数据配置类"""

    data: Dict[str, pl.DataFrame]
    base_data_key: str

    model_config = ConfigDict(arbitrary_types_allowed=True)


class OtherParams(BaseModel):
    """其他参数配置类，用于存放不太重要的参数"""

    brick_size: float = 2.0
    ha_timeframes: list[str] | None = None
    renko_timeframes: list[str] | None = None
