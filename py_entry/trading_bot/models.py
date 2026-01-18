from typing import List, Optional, Literal, Dict, Any, Union
from pydantic import BaseModel

# --- Common Structures ---


class BalanceStructure(BaseModel):
    free: Dict[str, float]
    used: Dict[str, float]
    total: Dict[str, float]
    timestamp: Optional[int] = None
    datetime: Optional[str] = None
    info: Optional[Dict[str, Any]] = None


class OrderStructure(BaseModel):
    id: str
    clientOrderId: Optional[str] = None
    datetime: Optional[str] = None
    timestamp: Optional[int] = None
    lastTradeTimestamp: Optional[int] = None
    status: str
    symbol: str
    type: str  # 'limit', 'market'
    side: str  # 'buy', 'sell'
    price: Optional[float] = None
    amount: Optional[float] = None
    filled: Optional[float] = None
    remaining: Optional[float] = None
    cost: Optional[float] = None
    average: Optional[float] = None
    trades: Optional[List[Any]] = None
    fee: Optional[Dict[str, Any]] = None
    info: Optional[Dict[str, Any]] = None
    triggerPrice: Optional[float] = None
    reduceOnly: Optional[bool] = None
    postOnly: Optional[bool] = None
    timeInForce: Optional[str] = None


class PositionStructure(BaseModel):
    symbol: str
    timestamp: Optional[int] = None
    datetime: Optional[str] = None
    contracts: Optional[float] = None
    contractSize: Optional[float] = None
    side: Optional[Literal["long", "short"]] = None
    notional: Optional[float] = None
    leverage: Optional[float] = None
    collateral: Optional[float] = None
    entryPrice: Optional[float] = None
    markPrice: Optional[float] = None
    liquidationPrice: Optional[float] = None
    hedged: Optional[bool] = None
    unrealizedPnl: Optional[float] = None
    percentage: Optional[float] = None
    maintenanceMargin: Optional[float] = None
    initialMargin: Optional[float] = None
    marginRatio: Optional[float] = None
    marginMode: Optional[str] = None
    info: Optional[Dict[str, Any]] = None


class TickerInfo(BaseModel):
    symbol: str
    timestamp: Optional[int] = None
    datetime: Optional[str] = None
    high: Optional[float] = None
    low: Optional[float] = None
    bid: Optional[float] = None
    bidVolume: Optional[float] = None
    ask: Optional[float] = None
    askVolume: Optional[float] = None
    vwap: Optional[float] = None
    open: Optional[float] = None
    close: Optional[float] = None
    last: Optional[float] = None
    previousClose: Optional[float] = None
    change: Optional[float] = None
    percentage: Optional[float] = None
    average: Optional[float] = None
    baseVolume: Optional[float] = None
    quoteVolume: Optional[float] = None
    info: Optional[Dict[str, Any]] = None


class TradeStructure(BaseModel):
    id: str
    timestamp: Optional[int] = None
    datetime: Optional[str] = None
    symbol: str
    order: Optional[str] = None
    type: Optional[str] = None
    side: Literal["buy", "sell"]
    takerOrMaker: Optional[str] = None
    price: float
    amount: float
    cost: float
    fee: Optional[Dict[str, Any]] = None
    info: Optional[Dict[str, Any]] = None


# --- Response Models ---


class BalanceResponse(BaseModel):
    balance: BalanceStructure


class TickersResponse(BaseModel):
    tickers: Dict[str, TickerInfo]


class MarketInfoResponse(BaseModel):
    symbol: str
    linear: bool
    settle: str
    precision_amount: float
    min_amount: float
    contract_size: float
    leverage: int


class OrderResponse(BaseModel):
    order: OrderStructure


class OrdersResponse(BaseModel):
    orders: List[OrderStructure]


class PositionsResponse(BaseModel):
    positions: List[PositionStructure]


class ClosePositionResponse(BaseModel):
    remaining_positions: List[PositionStructure]


class CancelAllOrdersResponse(BaseModel):
    result: Union[List[OrderStructure], Dict[str, Any], Any]


class TradesResponse(BaseModel):
    trades: List[TradeStructure]


class GenericResponse(BaseModel):
    result: Dict[str, Any]


# --- Request Models ---


class LimitOrderRequest(BaseModel):
    exchange_name: Literal["binance", "kraken"]
    market: Literal["future", "spot"]
    mode: Literal["sandbox", "live"] = "sandbox"
    symbol: str
    side: Literal["buy", "sell"]
    amount: float
    price: float
    clientOrderId: Optional[str] = None
    timeInForce: Optional[str] = None
    postOnly: bool = False


class MarketOrderRequest(BaseModel):
    exchange_name: Literal["binance", "kraken"]
    market: Literal["future", "spot"]
    mode: Literal["sandbox", "live"] = "sandbox"
    symbol: str
    side: Literal["buy", "sell"]
    amount: float
    clientOrderId: Optional[str] = None


class StopMarketOrderRequest(BaseModel):
    exchange_name: Literal["binance", "kraken"]
    market: Literal["future", "spot"]
    mode: Literal["sandbox", "live"] = "sandbox"
    symbol: str
    side: Literal["buy", "sell"]
    amount: float
    reduceOnly: bool = True
    triggerPrice: Optional[float] = None
    clientOrderId: Optional[str] = None
    timeInForce: Optional[str] = None


class TakeProfitMarketOrderRequest(BaseModel):
    exchange_name: Literal["binance", "kraken"]
    market: Literal["future", "spot"]
    mode: Literal["sandbox", "live"] = "sandbox"
    symbol: str
    side: Literal["buy", "sell"]
    amount: float
    reduceOnly: bool = True
    triggerPrice: Optional[float] = None
    clientOrderId: Optional[str] = None
    timeInForce: Optional[str] = None


class ClosePositionRequest(BaseModel):
    exchange_name: Literal["binance", "kraken"]
    market: Literal["future", "spot"]
    mode: Literal["sandbox", "live"] = "sandbox"
    symbol: str
    side: Optional[Literal["long", "short"]] = None


class CancelAllOrdersRequest(BaseModel):
    exchange_name: Literal["binance", "kraken"]
    market: Literal["future", "spot"]
    mode: Literal["sandbox", "live"] = "sandbox"
    symbol: Optional[str] = None


class SetLeverageRequest(BaseModel):
    exchange_name: Literal["binance", "kraken"]
    market: Literal["future", "spot"]
    mode: Literal["sandbox", "live"] = "sandbox"
    leverage: int
    symbol: Optional[str] = None


class SetMarginModeRequest(BaseModel):
    exchange_name: Literal["binance", "kraken"]
    market: Literal["future", "spot"]
    mode: Literal["sandbox", "live"] = "sandbox"
    marginMode: Literal["cross", "isolated"]
    symbol: Optional[str] = None


class CancelOrderRequest(BaseModel):
    exchange_name: Literal["binance", "kraken"]
    market: Literal["future", "spot"]
    mode: Literal["sandbox", "live"] = "sandbox"
    id: str
    symbol: Optional[str] = None
