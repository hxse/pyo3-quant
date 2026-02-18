"""
live 策略配置基类。

说明：
1. private live 直接复用 StrategyConfig 作为策略主体；
2. LiveStrategyConfig 仅承载 live 元信息（开关、交易品种、风控参数）；
3. private live 不依赖 py_entry/strategies 的 get_strategy。
"""

from dataclasses import dataclass
from typing import Literal

from py_entry.strategies.base import StrategyConfig


@dataclass
class LiveStrategyConfig:
    """live 策略注册信息（薄封装）。"""

    # live 策略主体，直接复用统一 StrategyConfig。
    strategy: StrategyConfig
    # 策略开关：False 表示注册但不进入机器人执行。
    enabled: bool = False
    # 机器人使用的基准周期键（如 ohlcv_15m）
    base_data_key: str = "ohlcv_15m"
    # 交易品种（如 BTC/USDT）
    symbol: str = "BTC/USDT"
    # 交易所参数
    exchange_name: Literal["binance", "kraken"] = "binance"
    market: Literal["future", "spot"] = "future"
    mode: Literal["sandbox", "live"] = "live"
    # 风控参数（传给 StrategyParams）
    position_size_pct: float = 1.0
    leverage: int = 1
    settlement_currency: str = "USDT"

    @property
    def name(self) -> str:
        """对外保留策略名访问。"""
        return self.strategy.name

    @property
    def description(self) -> str:
        """对外保留策略描述访问。"""
        return self.strategy.description
