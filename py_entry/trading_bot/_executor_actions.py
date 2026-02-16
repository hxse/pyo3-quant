from typing import Callable, Literal, Optional

from loguru import logger

from .callback_result import CallbackResult
from .callbacks import Callbacks
from .models import (
    CancelAllOrdersRequest,
    ClosePositionRequest,
    LimitOrderRequest,
    MarketOrderRequest,
    StopMarketOrderRequest,
    TakeProfitMarketOrderRequest,
)
from .signal import SignalAction
from .strategy_params import StrategyParams


# 统一 Side 映射函数签名，便于 ActionExecutor 复用同一规则。
MapSide = Callable[[Literal["long", "short"], bool], Literal["buy", "sell"]]


def execute_single_action(
    callbacks: Callbacks,
    params: StrategyParams,
    action: SignalAction,
    entry_order_type: Literal["limit", "market"],
    calculated_amount: Optional[float],
    map_side: MapSide,
) -> CallbackResult[bool]:
    """执行单个动作并返回统一结果。"""
    if action.action_type == "close_position":
        return _execute_close_position(callbacks, params, action)

    if action.action_type == "cancel_all_orders":
        return _execute_cancel_all_orders(callbacks, params, action)

    if action.action_type in ("create_limit_order", "create_market_order"):
        return _execute_entry_action(
            callbacks,
            params,
            action,
            entry_order_type,
            calculated_amount,
            map_side,
        )

    if action.action_type == "create_stop_market_order":
        if calculated_amount is None or calculated_amount <= 0:
            logger.warning(f"[{params.symbol}] 止损单跳过：无有效数量")
            return CallbackResult(success=True, data=True)
        return _execute_create_stop_order(
            callbacks,
            params,
            action,
            calculated_amount,
            map_side,
        )

    if action.action_type == "create_take_profit_market_order":
        if calculated_amount is None or calculated_amount <= 0:
            logger.warning(f"[{params.symbol}] 止盈单跳过：无有效数量")
            return CallbackResult(success=True, data=True)
        return _execute_create_tp_order(
            callbacks,
            params,
            action,
            calculated_amount,
            map_side,
        )

    logger.error(f"[{params.symbol}] 未知动作类型: {action.action_type}")
    return CallbackResult(
        success=False, message=f"Unknown action type: {action.action_type}"
    )


def _execute_entry_action(
    callbacks: Callbacks,
    params: StrategyParams,
    action: SignalAction,
    entry_order_type: Literal["limit", "market"],
    calculated_amount: Optional[float],
    map_side: MapSide,
) -> CallbackResult[bool]:
    """按配置执行开仓动作。"""
    if entry_order_type == "limit":
        if calculated_amount is None or calculated_amount <= 0:
            logger.warning(
                f"[{params.symbol}] 限价开仓跳过：无有效数量 (entry_order_type=limit)"
            )
            return CallbackResult(success=True, data=True)

        if action.price is None or action.price <= 0:
            logger.error(
                f"[{params.symbol}] Config is LIMIT but signal has no price. Skipping."
            )
            return CallbackResult(success=True, data=True)

        return _execute_create_limit_order(
            callbacks,
            params,
            action,
            calculated_amount,
            map_side,
        )

    if entry_order_type == "market":
        if calculated_amount is None or calculated_amount <= 0:
            logger.warning(
                f"[{params.symbol}] 市价开仓跳过：无有效数量 (entry_order_type=market)"
            )
            return CallbackResult(success=True, data=True)

        return _execute_create_market_order(
            callbacks,
            params,
            action,
            calculated_amount,
            map_side,
        )

    return CallbackResult(
        success=False, message=f"Invalid entry_order_type: {entry_order_type}"
    )


def _execute_close_position(
    callbacks: Callbacks,
    params: StrategyParams,
    action: SignalAction,
) -> CallbackResult[bool]:
    logger.info(f"[{params.symbol}] 执行平仓")
    result = callbacks.close_position(
        ClosePositionRequest(
            exchange_name=params.exchange_name,
            market=params.market,
            mode=params.mode,
            symbol=action.symbol,
            side=action.side,
        )
    )
    return CallbackResult(success=result.success, message=result.message)


def _execute_cancel_all_orders(
    callbacks: Callbacks,
    params: StrategyParams,
    action: SignalAction,
) -> CallbackResult[bool]:
    logger.info(f"[{params.symbol}] 取消所有挂单")
    result = callbacks.cancel_all_orders(
        CancelAllOrdersRequest(
            exchange_name=params.exchange_name,
            market=params.market,
            mode=params.mode,
            symbol=action.symbol,
        )
    )
    return CallbackResult(success=result.success, message=result.message)


def _execute_create_limit_order(
    callbacks: Callbacks,
    params: StrategyParams,
    action: SignalAction,
    amount: float,
    map_side: MapSide,
) -> CallbackResult[bool]:
    if action.side is None or action.price is None:
        return CallbackResult(
            success=False, message="Limit order requires side and price"
        )

    api_side = map_side(action.side, True)
    logger.info(
        f"[{params.symbol}] 限价开仓: side={api_side}, price={action.price}, amount={amount}"
    )

    result = callbacks.create_limit_order(
        LimitOrderRequest(
            exchange_name=params.exchange_name,
            market=params.market,
            mode=params.mode,
            symbol=action.symbol,
            side=api_side,
            amount=amount,
            price=action.price,
        )
    )
    return CallbackResult(success=result.success, message=result.message)


def _execute_create_market_order(
    callbacks: Callbacks,
    params: StrategyParams,
    action: SignalAction,
    amount: float,
    map_side: MapSide,
) -> CallbackResult[bool]:
    if action.side is None:
        return CallbackResult(success=False, message="Market order requires side")

    api_side = map_side(action.side, True)
    logger.info(f"[{params.symbol}] 市价开仓: side={api_side}, amount={amount}")

    result = callbacks.create_market_order(
        MarketOrderRequest(
            exchange_name=params.exchange_name,
            market=params.market,
            mode=params.mode,
            symbol=action.symbol,
            side=api_side,
            amount=amount,
        )
    )
    return CallbackResult(success=result.success, message=result.message)


def _execute_create_stop_order(
    callbacks: Callbacks,
    params: StrategyParams,
    action: SignalAction,
    amount: float,
    map_side: MapSide,
) -> CallbackResult[bool]:
    if action.side is None or action.price is None:
        return CallbackResult(
            success=False, message="Stop order requires side and price"
        )

    api_side = map_side(action.side, False)
    logger.info(
        f"[{params.symbol}] 挂止损单: side={api_side}, triggerPrice={action.price}, amount={amount}"
    )

    result = callbacks.create_stop_market_order(
        StopMarketOrderRequest(
            exchange_name=params.exchange_name,
            market=params.market,
            mode=params.mode,
            symbol=action.symbol,
            side=api_side,
            amount=amount,
            triggerPrice=action.price,
            reduceOnly=True,
        )
    )
    return CallbackResult(success=result.success, message=result.message)


def _execute_create_tp_order(
    callbacks: Callbacks,
    params: StrategyParams,
    action: SignalAction,
    amount: float,
    map_side: MapSide,
) -> CallbackResult[bool]:
    if action.side is None or action.price is None:
        return CallbackResult(success=False, message="TP order requires side and price")

    api_side = map_side(action.side, False)
    logger.info(
        f"[{params.symbol}] 挂止盈单: side={api_side}, triggerPrice={action.price}, amount={amount}"
    )

    result = callbacks.create_take_profit_market_order(
        TakeProfitMarketOrderRequest(
            exchange_name=params.exchange_name,
            market=params.market,
            mode=params.mode,
            symbol=action.symbol,
            side=api_side,
            amount=amount,
            triggerPrice=action.price,
            reduceOnly=True,
        )
    )
    return CallbackResult(success=result.success, message=result.message)
