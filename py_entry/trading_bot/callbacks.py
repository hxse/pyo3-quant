from typing import Protocol, List, Optional, Any, runtime_checkable
import polars as pl
from .callback_result import CallbackResult
from .signal import SignalState
from .strategy_params import StrategyParams
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


import pyo3_quant


@runtime_checkable
class Callbacks(Protocol):
    # --- Strategy & Backtest ---

    def get_strategy_params(self) -> CallbackResult[List[StrategyParams]]:
        """返回策略参数列表（每个元素对应一个策略/品种）"""
        ...

    def run_backtest(
        self, params: StrategyParams, df: pl.DataFrame
    ) -> CallbackResult[pl.DataFrame]:
        """运行回测获取信号 DataFrame"""
        ...

    def parse_signal(
        self, df: pl.DataFrame, params: StrategyParams, index: int = -1
    ) -> CallbackResult[SignalState]:
        """解析回测结果，支持指定行索引（默认 -1 为最后一行）"""
        try:
            row = df.row(index, named=True)
            # 调用 Rust 解析器 (pyo3_quant.backtest_engine.action_resolver.resolve_actions)
            # 注意：必须使用完整的属性路径访问 Rust 函数
            resolve_fn = pyo3_quant.backtest_engine.action_resolver.resolve_actions

            # Rust 返回字典 {"actions": [...], "has_exit": bool}
            raw_result = resolve_fn(
                row,
                params.symbol,
                params.sl_exit_in_bar,
                params.tp_exit_in_bar,
            )

            # 使用 Pydantic 验证并转换
            signal_state = SignalState.model_validate(raw_result)
            return CallbackResult(success=True, data=signal_state)
        except Exception as e:
            return CallbackResult(
                success=False, message=f"Signal parsing failed: {str(e)}"
            )

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
