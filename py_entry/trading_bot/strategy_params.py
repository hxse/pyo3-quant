from typing import Optional, Literal
from pydantic import BaseModel, Field


class StrategyParams(BaseModel):
    """策略参数，由 get_strategy_params 回调返回"""

    base_data_key: str = Field(..., description="基准周期，如 'ohlcv_15m'")
    symbol: str = Field(..., description="交易品种，如 'BTC/USDT'")

    # 风控模式
    sl_exit_in_bar: bool = Field(default=True, description="SL 是否使用 In-Bar 模式")
    tp_exit_in_bar: bool = Field(default=False, description="TP 是否使用 In-Bar 模式")

    # 仓位计算
    position_size_pct: float = Field(
        default=1.0, ge=0.0, le=1.0, description="仓位比例 0.0~1.0"
    )
    leverage: int = Field(default=1, ge=1, description="杠杆倍数")

    # 交易所配置
    exchange_name: Literal["binance", "kraken"] = Field(default="binance")
    market: Literal["future", "spot"] = Field(default="future")
    mode: Literal["sandbox", "live"] = Field(default="sandbox")

    # 结算配置
    settlement_currency: str = Field(
        default="USDT", description="结算币种，如 USDT, BTC, USDC"
    )
