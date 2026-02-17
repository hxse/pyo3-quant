from typing import Optional

from loguru import logger

from .bot_config import BotConfig
from .callbacks import Callbacks
from .executor import ActionExecutor
from .runtime_checks import RuntimeChecks
from .signal import SignalAction, SignalState
from .strategy_params import StrategyParams

ENTRY_ACTION_TYPES = ("create_limit_order", "create_market_order")
ENTRY_FOLLOWUP_ACTION_TYPES = (
    "create_stop_market_order",
    "create_take_profit_market_order",
)


class StepResult:
    """单步执行结果"""

    def __init__(self, success: bool, message: Optional[str] = None):
        self.success = success
        self.message = message


def execute_signal(
    callbacks: Callbacks,
    config: BotConfig,
    params: StrategyParams,
    curr_signal: SignalState,
    prev_signal: SignalState,
    runtime_checks: RuntimeChecks,
    executor: ActionExecutor,
) -> StepResult:
    """执行信号动作"""
    if not curr_signal.actions:
        logger.debug(f"[{params.symbol}] 无动作")
        return StepResult(success=True)

    # 提取开仓动作，用于后续开仓前检查。
    entry_actions = [
        action
        for action in curr_signal.actions
        if action.action_type in ENTRY_ACTION_TYPES
    ]
    has_exit_action = any(
        action.action_type == "close_position" for action in curr_signal.actions
    )
    has_entry = len(entry_actions) > 0
    should_skip_entry_actions = False

    # 1. 孤儿订单检查（条件触发）。
    if runtime_checks.should_trigger_orphan_check(curr_signal, prev_signal):
        orphan_result = runtime_checks.orphan_order_check(params)
        if not orphan_result.success:
            return StepResult(success=False, message=orphan_result.message)

    calculated_amount: Optional[float] = None

    # 2. 开仓前检查。
    if has_entry:
        entry_action = entry_actions[0]
        signal_side = entry_action.side
        entry_price = entry_action.price

        if signal_side is None:
            return StepResult(success=False, message="Entry action requires side")

        # 2a. 纯开仓场景才做重复开仓检查。
        # 反手信号本身带离场动作，不应在离场前被重复开仓检查短路。
        if not has_exit_action:
            dup_result = runtime_checks.duplicate_entry_check(params, signal_side)
            if not dup_result.success:
                return StepResult(success=False, message=dup_result.message)
            if dup_result.data == "skip":
                should_skip_entry_actions = True

        if not should_skip_entry_actions:
            # 2b. 计算下单数量。
            if entry_price is None:
                ticker_result = callbacks.fetch_tickers(
                    exchange_name=params.exchange_name,
                    market=params.market,
                    mode=params.mode,
                    symbols=params.symbol,
                )
                if not ticker_result.success:
                    return StepResult(
                        success=False,
                        message=f"fetch_tickers failed: {ticker_result.message}",
                    )

                tickers_resp = ticker_result.data
                ticker_info = (
                    tickers_resp.tickers.get(params.symbol)
                    if tickers_resp and tickers_resp.tickers
                    else None
                )

                if ticker_info:
                    entry_price = ticker_info.last or ticker_info.close or 0.0
                else:
                    entry_price = 0.0

                if entry_price <= 0:
                    return StepResult(
                        success=False,
                        message=f"Invalid ticker price for {params.symbol}",
                    )

            if entry_price > 0:
                amount_result = runtime_checks.calculate_order_amount(
                    params, entry_price
                )
                if not amount_result.success:
                    return StepResult(success=False, message=amount_result.message)
                calculated_amount = amount_result.data

                if calculated_amount is None:
                    return StepResult(
                        success=False, message="Calculated amount is None"
                    )

                # 2c. 最小订单检查。
                min_result = runtime_checks.min_order_check(
                    params, calculated_amount, entry_price
                )
                if not min_result.success:
                    return StepResult(success=False, message=min_result.message)
                if min_result.data == "fail":
                    should_skip_entry_actions = True

    actions_to_execute = (
        _filter_non_entry_actions(curr_signal.actions)
        if should_skip_entry_actions
        else curr_signal.actions
    )
    if not actions_to_execute:
        logger.info(f"[{params.symbol}] 开仓被跳过，且无其他动作需要执行")
        return StepResult(success=True)

    # 3. 执行动作。
    exec_result = executor.execute_actions(
        params=params,
        actions=actions_to_execute,
        entry_order_type=config.entry_order_type,
        calculated_amount=calculated_amount,
    )

    return StepResult(success=exec_result.success, message=exec_result.message)


def _filter_non_entry_actions(actions: list[SignalAction]) -> list[SignalAction]:
    """过滤掉开仓及其同方向附属动作（SL/TP），保留离场等其他动作。"""
    return [
        action
        for action in actions
        if action.action_type not in ENTRY_ACTION_TYPES + ENTRY_FOLLOWUP_ACTION_TYPES
    ]
