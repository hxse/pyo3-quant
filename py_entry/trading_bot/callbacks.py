from typing import Protocol, List, Optional, Any, runtime_checkable
from .callback_result import CallbackResult
from .models import (
    BalanceResponse,
    TickersResponse,
    MarketInfoResponse,
    PositionsResponse,
    OrdersResponse,
    OrderResponse,
    ClosePositionResponse,
    CancelAllOrdersResponse,
    GenericResponse,
    LimitOrderRequest,
    MarketOrderRequest,
    StopMarketOrderRequest,
    TakeProfitMarketOrderRequest,
    ClosePositionRequest,
    CancelAllOrdersRequest,
    SetLeverageRequest,
    SetMarginModeRequest,
    CancelOrderRequest,
)


@runtime_checkable
class Callbacks(Protocol):
    # --- Data & Query (GET with params) ---

    def fetch_balance(
        self, exchange_name: str, market: str, mode: str
    ) -> CallbackResult[BalanceResponse]: ...

    def fetch_tickers(
        self, exchange_name: str, market: str, mode: str, symbols: Optional[str]
    ) -> CallbackResult[TickersResponse]: ...

    def fetch_ohlcv(
        self,
        exchange_name: str,
        market: str,
        mode: str,
        symbol: str,
        timeframe: str,
        since: Optional[int],
        limit: Optional[int],
        enable_cache: bool,
        enable_test: bool,
    ) -> CallbackResult[List[List[float]]]: ...

    def fetch_market_info(
        self, exchange_name: str, market: str, mode: str, symbol: str
    ) -> CallbackResult[MarketInfoResponse]: ...

    def fetch_positions(
        self, exchange_name: str, market: str, mode: str, symbols: Optional[List[str]]
    ) -> CallbackResult[PositionsResponse]: ...

    def fetch_open_orders(
        self,
        exchange_name: str,
        market: str,
        mode: str,
        symbol: Optional[str],
        since: Optional[int],
        limit: Optional[int],
    ) -> CallbackResult[OrdersResponse]: ...

    def fetch_closed_orders(
        self,
        exchange_name: str,
        market: str,
        mode: str,
        symbol: Optional[str],
        since: Optional[int],
        limit: Optional[int],
    ) -> CallbackResult[OrdersResponse]: ...

    def fetch_my_trades(
        self,
        exchange_name: str,
        market: str,
        mode: str,
        symbol: Optional[str],
        since: Optional[int],
        limit: Optional[int],
    ) -> CallbackResult[OrdersResponse]: ...

    # --- Order Execution & Management (POST with Body) ---

    def create_limit_order(
        self, request: LimitOrderRequest
    ) -> CallbackResult[OrderResponse]: ...

    def create_market_order(
        self, request: MarketOrderRequest
    ) -> CallbackResult[OrderResponse]: ...

    def create_stop_market_order(
        self, request: StopMarketOrderRequest
    ) -> CallbackResult[OrderResponse]: ...

    def create_take_profit_market_order(
        self, request: TakeProfitMarketOrderRequest
    ) -> CallbackResult[OrderResponse]: ...

    def close_position(
        self, request: ClosePositionRequest
    ) -> CallbackResult[ClosePositionResponse]: ...

    def cancel_all_orders(
        self, request: CancelAllOrdersRequest
    ) -> CallbackResult[CancelAllOrdersResponse]: ...

    def cancel_order(
        self, request: CancelOrderRequest
    ) -> CallbackResult[OrderResponse]: ...

    # --- Account Settings (POST with Body) ---

    def set_leverage(
        self, request: SetLeverageRequest
    ) -> CallbackResult[GenericResponse]: ...

    def set_margin_mode(
        self, request: SetMarginModeRequest
    ) -> CallbackResult[GenericResponse]: ...
