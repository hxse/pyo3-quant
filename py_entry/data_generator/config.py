from dataclasses import dataclass
from typing import Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict
import polars as pl
from py_entry.io.types import RequestConfig

MarketType = Literal["future", "spot"]
ModeType = Literal["sandbox", "live"]


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
    align_to_base_range: bool = False

    model_config = ConfigDict(arbitrary_types_allowed=True)


class OhlcvDataFetchConfig(BaseModel):
    """OHLCV数据获取配置类（用户层，支持多周期）"""

    config: RequestConfig
    exchange_name: str = "binance"
    market: MarketType = "future"
    symbol: str = "BTC/USDT"
    timeframes: list[str]
    since: int | None = None
    limit: int | None = None
    enable_cache: bool = True
    enable_test: bool = False
    mode: ModeType = "sandbox"
    base_data_key: str
    align_to_base_range: bool = False


@dataclass
class OhlcvRequestParams:
    """OHLCV单次请求参数（内部使用，由 OhlcvDataFetchConfig 转换而来）"""

    config: RequestConfig
    exchange_name: str
    market: MarketType
    symbol: str
    timeframe: str  # 注意：这里是单周期，从 timeframes 展开
    since: int | None = None
    limit: int | None = None
    enable_cache: bool = True
    enable_test: bool = False
    mode: ModeType = "sandbox"


class DirectDataConfig(BaseModel):
    """直接数据配置类"""

    data: Dict[str, pl.DataFrame]
    base_data_key: str
    align_to_base_range: bool = False

    model_config = ConfigDict(arbitrary_types_allowed=True)


class OtherParams(BaseModel):
    """其他参数配置类，用于存放不太重要的参数"""

    brick_size: float = 2.0
    ha_timeframes: list[str] | None = None
    renko_timeframes: list[str] | None = None
