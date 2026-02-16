"""RuntimeChecks 逻辑实现模块。"""

import math
from typing import Literal

from loguru import logger

from .callback_result import CallbackResult
from .callbacks import Callbacks
from .models import CancelAllOrdersRequest
from .signal import SignalState
from .strategy_params import StrategyParams


def should_trigger_orphan_check(
    curr_signal: SignalState,
    prev_signal: SignalState,
) -> bool:
    """判断是否触发孤儿订单检查。"""
    # 条件1: 当前信号即将开仓。
    has_entry = any(
        action.action_type in ("create_limit_order", "create_market_order")
        for action in curr_signal.actions
    )
    # 条件2: 上一根存在限价进场。
    prev_has_limit = any(
        action.action_type == "create_limit_order" for action in prev_signal.actions
    )
    # 条件3: 上一根存在离场。
    prev_has_exit = prev_signal.has_exit

    return has_entry or prev_has_limit or prev_has_exit


def orphan_order_check(
    callbacks: Callbacks,
    params: StrategyParams,
) -> CallbackResult[bool]:
    """孤儿订单检查。"""
    result = callbacks.fetch_positions(
        exchange_name=params.exchange_name,
        market=params.market,
        mode=params.mode,
        symbols=[params.symbol],
    )
    if not result.success:
        return CallbackResult(
            success=False, message=f"fetch_positions failed: {result.message}"
        )

    positions = result.data.positions if result.data else []
    has_position = any(
        position.symbol == params.symbol
        and position.contracts
        and position.contracts > 0
        for position in positions
    )

    if not has_position:
        logger.info(f"[{params.symbol}] 孤儿订单检查：无持仓，清理所有挂单")
        cancel_result = callbacks.cancel_all_orders(
            CancelAllOrdersRequest(
                exchange_name=params.exchange_name,
                market=params.market,
                mode=params.mode,
                symbol=params.symbol,
            )
        )
        if not cancel_result.success:
            return CallbackResult(
                success=False,
                message=f"cancel_all_orders failed: {cancel_result.message}",
            )

    return CallbackResult(success=True, data=True)


def duplicate_entry_check(
    callbacks: Callbacks,
    params: StrategyParams,
    signal_side: Literal["long", "short"],
) -> CallbackResult[Literal["proceed", "skip"]]:
    """重复开仓检查。"""
    result = callbacks.fetch_positions(
        exchange_name=params.exchange_name,
        market=params.market,
        mode=params.mode,
        symbols=[params.symbol],
    )
    if not result.success:
        return CallbackResult(
            success=False, message=f"fetch_positions failed: {result.message}"
        )

    positions = result.data.positions if result.data else []
    for position in positions:
        if (
            position.symbol == params.symbol
            and position.contracts
            and position.contracts > 0
        ):
            if position.side == signal_side:
                logger.info(
                    f"[{params.symbol}] 重复开仓检查：已有 {position.side} 持仓，跳过开仓"
                )
                return CallbackResult(success=True, data="skip")

            logger.warning(
                f"[{params.symbol}] 重复开仓检查：已有 {position.side} 持仓但信号为 {signal_side}，跳过"
            )
            return CallbackResult(success=True, data="skip")

    return CallbackResult(success=True, data="proceed")


def calculate_order_amount(
    callbacks: Callbacks,
    params: StrategyParams,
    entry_price: float,
) -> CallbackResult[float]:
    """计算下单数量。"""
    balance_result = callbacks.fetch_balance(
        exchange_name=params.exchange_name,
        market=params.market,
        mode=params.mode,
    )
    if not balance_result.success:
        return CallbackResult(
            success=False, message=f"fetch_balance failed: {balance_result.message}"
        )

    currency = params.settlement_currency
    free_balance = (
        balance_result.data.balance.free.get(currency, 0.0)
        if balance_result.data
        else 0.0
    )

    market_result = callbacks.fetch_market_info(
        exchange_name=params.exchange_name,
        market=params.market,
        mode=params.mode,
        symbol=params.symbol,
    )
    if not market_result.success:
        return CallbackResult(
            success=False,
            message=f"fetch_market_info failed: {market_result.message}",
        )

    if not market_result.data:
        return CallbackResult(
            success=False, message="fetch_market_info returned no data"
        )

    precision_amount = market_result.data.precision_amount
    position_value = free_balance * params.position_size_pct * params.leverage
    raw_amount = position_value / entry_price

    # 统一按 step size 解释 precision_amount。
    try:
        step_size = float(precision_amount)
    except (ValueError, TypeError):
        logger.error(f"Invalid precision_amount: {precision_amount}, defaulting to 1.0")
        step_size = 1.0

    if step_size <= 0:
        logger.warning(f"Invalid step_size {step_size} <= 0, defaulting to 1.0")
        step_size = 1.0

    steps = math.floor(raw_amount / step_size + 1e-10)
    final_amount = steps * step_size

    logger.debug(
        f"[{params.symbol}] 下单计算: 余额={free_balance}, 仓位={params.position_size_pct}, "
        f"杠杆={params.leverage}, 价格={entry_price}, 数量={final_amount}, 步长={step_size}"
    )

    return CallbackResult(success=True, data=final_amount)


def min_order_check(
    callbacks: Callbacks,
    params: StrategyParams,
    amount: float,
) -> CallbackResult[Literal["pass", "fail"]]:
    """最小订单检查。"""
    market_result = callbacks.fetch_market_info(
        exchange_name=params.exchange_name,
        market=params.market,
        mode=params.mode,
        symbol=params.symbol,
    )
    if not market_result.success:
        return CallbackResult(
            success=False,
            message=f"fetch_market_info failed: {market_result.message}",
        )

    if not market_result.data:
        return CallbackResult(
            success=False, message="fetch_market_info returned no data"
        )

    precision_amount = market_result.data.precision_amount
    min_amount = market_result.data.min_amount

    try:
        precision_val = float(precision_amount)
    except (ValueError, TypeError):
        return CallbackResult(
            success=False,
            message=f"Invalid precision_amount (not a number): {precision_amount}",
        )

    if precision_val <= 0:
        return CallbackResult(
            success=False,
            message=f"Invalid precision_amount (<= 0): {precision_amount}",
        )

    if min_amount <= 0:
        min_amount = precision_val

    if amount < min_amount:
        logger.warning(
            f"[{params.symbol}] 最小订单检查失败：数量 {amount} < 最小数量 {min_amount}"
        )
        return CallbackResult(success=True, data="fail")

    return CallbackResult(success=True, data="pass")
