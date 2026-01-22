import polars as pl
from typing import Any, List, Optional
from loguru import logger

from .callback_result import CallbackResult
from .callbacks import Callbacks
from .strategy_params import StrategyParams
from .signal import SignalState
from .models import (
    PositionsResponse,
    CancelAllOrdersResponse,
    LimitOrderRequest,
    MarketOrderRequest,
    StopMarketOrderRequest,
    TakeProfitMarketOrderRequest,
    ClosePositionRequest,
    CancelAllOrdersRequest,
    BalanceResponse,
    TickersResponse,
    MarketInfoResponse,
    OrdersResponse,
    OrderResponse,
    ClosePositionResponse,
    GenericResponse,
    CancelOrderRequest,
    SetLeverageRequest,
    SetMarginModeRequest,
)


class OptimizationCallbacks:
    """
    作用域内的 API 优化代理。
    生命周期：仅限于单次 Loop 的单个 Symbol 处理过程。

    功能：
    1. 缓存 fetch_positions (仅针对当前 symbol)
    2. 自动失效 (下单/平仓操作)
    3. 去重 cancel_all_orders (仅针对当前 symbol)
    4. 显式实现 Callbacks 协议，提供完整的类型提示
    """

    def __init__(self, inner: Callbacks, symbol: str):
        self._inner = inner
        self._symbol = symbol

        # 状态存储
        self._positions_cache: Optional[PositionsResponse] = None
        self._cancelled_all: bool = False

    # --- Strategy & Backtest (Pass-through) ---

    def get_strategy_params(self) -> CallbackResult[List[StrategyParams]]:
        return self._inner.get_strategy_params()

    def run_backtest(
        self, params: StrategyParams, df: pl.DataFrame
    ) -> CallbackResult[pl.DataFrame]:
        return self._inner.run_backtest(params, df)

    def parse_signal(
        self, df: pl.DataFrame, params: StrategyParams, index: int = -1
    ) -> CallbackResult[SignalState]:
        return self._inner.parse_signal(df, params, index)

    # --- Data & Query (Pass-through) ---

    def fetch_balance(
        self, exchange_name: str, market: str, mode: str
    ) -> CallbackResult[BalanceResponse]:
        return self._inner.fetch_balance(exchange_name, market, mode)

    def fetch_tickers(
        self, exchange_name: str, market: str, mode: str, symbols: Optional[str]
    ) -> CallbackResult[TickersResponse]:
        return self._inner.fetch_tickers(exchange_name, market, mode, symbols)

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
    ) -> CallbackResult[List[List[float]]]:
        return self._inner.fetch_ohlcv(
            exchange_name,
            market,
            mode,
            symbol,
            timeframe,
            since,
            limit,
            enable_cache,
            enable_test,
        )

    def fetch_market_info(
        self, exchange_name: str, market: str, mode: str, symbol: str
    ) -> CallbackResult[MarketInfoResponse]:
        return self._inner.fetch_market_info(exchange_name, market, mode, symbol)

    def fetch_open_orders(
        self,
        exchange_name: str,
        market: str,
        mode: str,
        symbol: Optional[str],
        since: Optional[int],
        limit: Optional[int],
    ) -> CallbackResult[OrdersResponse]:
        return self._inner.fetch_open_orders(
            exchange_name, market, mode, symbol, since, limit
        )

    def fetch_closed_orders(
        self,
        exchange_name: str,
        market: str,
        mode: str,
        symbol: Optional[str],
        since: Optional[int],
        limit: Optional[int],
    ) -> CallbackResult[OrdersResponse]:
        return self._inner.fetch_closed_orders(
            exchange_name, market, mode, symbol, since, limit
        )

    def fetch_my_trades(
        self,
        exchange_name: str,
        market: str,
        mode: str,
        symbol: Optional[str],
        since: Optional[int],
        limit: Optional[int],
    ) -> CallbackResult[OrdersResponse]:
        return self._inner.fetch_my_trades(
            exchange_name, market, mode, symbol, since, limit
        )

    # --- Optimized Read Requests ---

    def fetch_positions(
        self, exchange_name: str, market: str, mode: str, symbols: Optional[List[str]]
    ) -> CallbackResult[PositionsResponse]:
        # 优化条件：仅查询当前 symbol
        if symbols == [self._symbol] and self._positions_cache:
            logger.debug(f"[{self._symbol}] fetch_positions: Cache Hit")
            return CallbackResult(success=True, data=self._positions_cache)

        result = self._inner.fetch_positions(exchange_name, market, mode, symbols)

        # 缓存写入条件：请求成功，且 symbol 匹配
        if result.success and symbols == [self._symbol]:
            self._positions_cache = result.data

        return result

    # --- Cache Invalidation Helpers ---

    def _invalidate_cache(self, strict: bool = True):
        """让持仓缓存失效，strict=True 表示同时失效 '已全部取消' 状态"""
        self._positions_cache = None
        if strict:
            self._cancelled_all = False

    # --- Optimized Write Requests (Invalidation) ---

    def create_limit_order(
        self, request: LimitOrderRequest
    ) -> CallbackResult[OrderResponse]:
        self._invalidate_cache(strict=True)
        return self._inner.create_limit_order(request)

    def create_market_order(
        self, request: MarketOrderRequest
    ) -> CallbackResult[OrderResponse]:
        # 市价单通常立即成交或 IOC/FOK，不会留下挂单，因此不需要重置 cancelled_all
        self._invalidate_cache(strict=False)
        return self._inner.create_market_order(request)

    def create_stop_market_order(
        self, request: StopMarketOrderRequest
    ) -> CallbackResult[OrderResponse]:
        self._invalidate_cache(strict=True)
        return self._inner.create_stop_market_order(request)

    def create_take_profit_market_order(
        self, request: TakeProfitMarketOrderRequest
    ) -> CallbackResult[OrderResponse]:
        self._invalidate_cache(strict=True)
        return self._inner.create_take_profit_market_order(request)

    def close_position(
        self, request: ClosePositionRequest
    ) -> CallbackResult[ClosePositionResponse]:
        # 平仓只影响持仓，不增加挂单，所以不需要重置 cancelled_all
        self._invalidate_cache(strict=False)
        return self._inner.close_position(request)

    def cancel_order(
        self, request: CancelOrderRequest
    ) -> CallbackResult[OrderResponse]:
        # 取消单个订单不影响 _cancelled_all 状态（除非刚好取消了最后一个，但我们无法简单得知）
        # 也不影响持仓缓存
        return self._inner.cancel_order(request)

    # --- Optimized Dedup Requests ---

    def cancel_all_orders(
        self, request: CancelAllOrdersRequest
    ) -> CallbackResult[CancelAllOrdersResponse]:
        # 仅针对当前 symbol 去重
        if request.symbol == self._symbol:
            if self._cancelled_all:
                logger.debug(f"[{self._symbol}] cancel_all_orders: Dedup Skip")
                # 模拟成功返回
                return CallbackResult(
                    success=True, data=CancelAllOrdersResponse(result=[])
                )

        result = self._inner.cancel_all_orders(request)

        if result.success and request.symbol == self._symbol:
            self._cancelled_all = True

        return result

    # --- Account Settings (Pass-through) ---

    def set_leverage(
        self, request: SetLeverageRequest
    ) -> CallbackResult[GenericResponse]:
        return self._inner.set_leverage(request)

    def set_margin_mode(
        self, request: SetMarginModeRequest
    ) -> CallbackResult[GenericResponse]:
        return self._inner.set_margin_mode(request)
