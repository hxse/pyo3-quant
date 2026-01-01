"""
数据生成器配置类
"""

from dataclasses import dataclass
from typing import Dict, Optional
import polars as pl

from py_entry.io.types import RequestConfig


@dataclass
class DataGenerationParams:
    """数据生成参数配置类

    Attributes:
        timeframes: 时间周期列表
        start_time: 起始时间戳 (毫秒)
        num_bars: K线数量
        base_data_key: 基准数据键
        fixed_seed: 随机种子
        volatility: 波动率 (默认 0.02 = 2%)
        trend: 趋势系数 (默认 0，正值上涨趋势，负值下跌趋势)
        gap_factor: 跳空因子 (默认 0.5，越大跳空越频繁)
        extreme_prob: 极端行情概率 (默认 0，范围 0-1)
        extreme_mult: 极端行情波动倍数 (默认 3)
    """

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


@dataclass
class OhlcvDataFetchConfig:
    """OHLCV数据获取配置类"""

    config: RequestConfig
    timeframes: list[str]
    start_time: int
    count: int
    enable_cache: bool
    base_data_key: str


@dataclass
class DirectDataConfig:
    """直接数据配置类"""

    data: Dict[str, pl.DataFrame]
    base_data_key: str


@dataclass
class OtherParams:
    """其他参数配置类，用于存放不太重要的参数"""

    brick_size: float = 2.0
    ha_timeframes: list[str] | None = None
    renko_timeframes: list[str] | None = None
