from typing import List, Optional, Any, Dict
import polars as pl


from py_entry.trading_bot import (
    CallbackResult,
    StrategyParams,
    SignalState,
    TickersResponse,
    TickerInfo,
    BalanceResponse,
    BalanceStructure,
    MarketInfoResponse,
    PositionsResponse,
    PositionStructure,
    OrderResponse,
    OrderStructure,
    OrdersResponse,
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


class MockCallbacks:
    """可配置的 Mock 回调集合"""

    def __init__(self):
        self.call_log: List[Dict[str, Any]] = []

        # 可配置的返回值
        self.strategy_params: List[StrategyParams] = [
            StrategyParams(base_data_key="ohlcv_15m", symbol="BTC/USDT")
        ]
        self.positions: List[PositionStructure] = []
        self.balance = BalanceStructure(
            free={"USDT": 10000.0},
            used={"USDT": 0.0},
            total={"USDT": 10000.0},
        )
        self.market_info = MarketInfoResponse(
            symbol="BTC/USDT",
            linear=True,
            settle="USDT",
            precision_amount=0.001,
            min_amount=0.001,
            contract_size=1.0,
            leverage=1,
        )
        self.signal_states: Dict[int, SignalState] = {
            -1: SignalState(actions=[]),
            -2: SignalState(actions=[]),
        }

    def _log(self, method: str, **kwargs):
        self.call_log.append({"method": method, **kwargs})

    # --- Strategy & Backtest ---

    def get_strategy_params(self) -> CallbackResult[List[StrategyParams]]:
        self._log("get_strategy_params")
        return CallbackResult(success=True, data=self.strategy_params)

    def run_backtest(
        self, params: StrategyParams, df: pl.DataFrame
    ) -> CallbackResult[pl.DataFrame]:
        self._log("run_backtest", symbol=params.symbol)
        return CallbackResult(success=True, data=df)

    def parse_signal(
        self, df: pl.DataFrame, params: StrategyParams, index: int = -1
    ) -> CallbackResult[SignalState]:
        self._log("parse_signal", symbol=params.symbol, index=index)
        return CallbackResult(
            success=True, data=self.signal_states.get(index, SignalState(actions=[]))
        )

    # --- Data & Query ---

    def fetch_balance(
        self, exchange_name: str, market: str, mode: str
    ) -> CallbackResult[BalanceResponse]:
        self._log("fetch_balance")
        return CallbackResult(success=True, data=BalanceResponse(balance=self.balance))

    def fetch_tickers(
        self, exchange_name: str, market: str, mode: str, symbols: Optional[str]
    ) -> CallbackResult[Any]:
        self._log("fetch_tickers", symbols=symbols)
        return CallbackResult(
            success=True,
            data=TickersResponse(
                tickers={
                    "BTC/USDT": TickerInfo(
                        symbol="BTC/USDT",
                        high=50500.0,
                        low=49500.0,
                        bid=50000.0,
                        bidVolume=1.0,
                        ask=50010.0,
                        askVolume=1.0,
                        vwap=50005.0,
                        open=50000.0,
                        close=50000.0,
                        last=50000.0,
                        baseVolume=100.0,
                        quoteVolume=5000000.0,
                        timestamp=1700000000000,
                    )
                }
            ),
        )

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
        self._log("fetch_ohlcv", symbol=symbol, timeframe=timeframe)
        # 返回假数据
        return CallbackResult(
            success=True,
            data=[
                [1700000000000, 50000.0, 50100.0, 49900.0, 50050.0, 1000.0],
                [1700000900000, 50050.0, 50200.0, 50000.0, 50150.0, 1200.0],
            ],
        )

    def fetch_market_info(
        self, exchange_name: str, market: str, mode: str, symbol: str
    ) -> CallbackResult[MarketInfoResponse]:
        self._log("fetch_market_info", symbol=symbol)
        return CallbackResult(success=True, data=self.market_info)

    def fetch_positions(
        self, exchange_name: str, market: str, mode: str, symbols: Optional[List[str]]
    ) -> CallbackResult[PositionsResponse]:
        self._log("fetch_positions", symbols=symbols)
        return CallbackResult(
            success=True, data=PositionsResponse(positions=self.positions)
        )

    def fetch_open_orders(
        self,
        exchange_name: str,
        market: str,
        mode: str,
        symbol: Optional[str],
        since: Optional[int],
        limit: Optional[int],
    ) -> CallbackResult[OrdersResponse]:
        self._log("fetch_open_orders", symbol=symbol)
        return CallbackResult(success=True, data=OrdersResponse(orders=[]))

    def fetch_closed_orders(
        self,
        exchange_name: str,
        market: str,
        mode: str,
        symbol: Optional[str],
        since: Optional[int],
        limit: Optional[int],
    ) -> CallbackResult[OrdersResponse]:
        self._log("fetch_closed_orders", symbol=symbol)
        return CallbackResult(success=True, data=OrdersResponse(orders=[]))

    def fetch_my_trades(
        self,
        exchange_name: str,
        market: str,
        mode: str,
        symbol: Optional[str],
        since: Optional[int],
        limit: Optional[int],
    ) -> CallbackResult[OrdersResponse]:
        self._log("fetch_my_trades", symbol=symbol)
        return CallbackResult(success=True, data=OrdersResponse(orders=[]))

    # --- Order Execution ---

    def create_limit_order(
        self, request: LimitOrderRequest
    ) -> CallbackResult[OrderResponse]:
        self._log("create_limit_order", request=request.model_dump())
        return CallbackResult(
            success=True,
            data=OrderResponse(
                order=OrderStructure(
                    id="mock_order_001",
                    status="open",
                    symbol=request.symbol,
                    type="limit",
                    side=request.side,
                    price=request.price,
                    amount=request.amount,
                )
            ),
        )

    def create_market_order(
        self, request: MarketOrderRequest
    ) -> CallbackResult[OrderResponse]:
        self._log("create_market_order", request=request.model_dump())
        return CallbackResult(
            success=True,
            data=OrderResponse(
                order=OrderStructure(
                    id="mock_order_002",
                    status="closed",
                    symbol=request.symbol,
                    type="market",
                    side=request.side,
                    amount=request.amount,
                )
            ),
        )

    def create_stop_market_order(
        self, request: StopMarketOrderRequest
    ) -> CallbackResult[OrderResponse]:
        self._log("create_stop_market_order", request=request.model_dump())
        return CallbackResult(
            success=True,
            data=OrderResponse(
                order=OrderStructure(
                    id="mock_order_003",
                    status="open",
                    symbol=request.symbol,
                    type="stop_market",
                    side=request.side,
                    amount=request.amount,
                    triggerPrice=request.triggerPrice,
                )
            ),
        )

    def create_take_profit_market_order(
        self, request: TakeProfitMarketOrderRequest
    ) -> CallbackResult[OrderResponse]:
        self._log("create_take_profit_market_order", request=request.model_dump())
        return CallbackResult(
            success=True,
            data=OrderResponse(
                order=OrderStructure(
                    id="mock_order_004",
                    status="open",
                    symbol=request.symbol,
                    type="take_profit_market",
                    side=request.side,
                    amount=request.amount,
                    triggerPrice=request.triggerPrice,
                )
            ),
        )

    def close_position(
        self, request: ClosePositionRequest
    ) -> CallbackResult[ClosePositionResponse]:
        self._log("close_position", request=request.model_dump())
        return CallbackResult(
            success=True, data=ClosePositionResponse(remaining_positions=[])
        )

    def cancel_all_orders(
        self, request: CancelAllOrdersRequest
    ) -> CallbackResult[CancelAllOrdersResponse]:
        self._log("cancel_all_orders", request=request.model_dump())
        return CallbackResult(success=True, data=CancelAllOrdersResponse(result=[]))

    def cancel_order(
        self, request: CancelOrderRequest
    ) -> CallbackResult[OrderResponse]:
        self._log("cancel_order", request=request.model_dump())
        return CallbackResult(
            success=True,
            data=OrderResponse(
                order=OrderStructure(
                    id=request.id,
                    status="canceled",
                    symbol=request.symbol or "",
                    type="",
                    side="buy",
                )
            ),
        )

    # --- Account Settings ---

    def set_leverage(
        self, request: SetLeverageRequest
    ) -> CallbackResult[GenericResponse]:
        self._log("set_leverage", request=request.model_dump())
        return CallbackResult(success=True, data=GenericResponse(result={}))

    def set_margin_mode(
        self, request: SetMarginModeRequest
    ) -> CallbackResult[GenericResponse]:
        self._log("set_margin_mode", request=request.model_dump())
        return CallbackResult(success=True, data=GenericResponse(result={}))
