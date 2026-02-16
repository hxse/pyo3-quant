from typing import Optional

from loguru import logger

from .bot_config import BotConfig
from .callbacks import Callbacks
from .executor import ActionExecutor
from .runtime_checks import RuntimeChecks
from .signal import SignalState
from .strategy_params import StrategyParams


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
        if action.action_type in ("create_limit_order", "create_market_order")
    ]
    has_entry = len(entry_actions) > 0

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

        # 2a. 重复开仓检查。
        dup_result = runtime_checks.duplicate_entry_check(params, signal_side)
        if not dup_result.success:
            return StepResult(success=False, message=dup_result.message)
        if dup_result.data == "skip":
            return StepResult(success=True)

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
            amount_result = runtime_checks.calculate_order_amount(params, entry_price)
            if not amount_result.success:
                return StepResult(success=False, message=amount_result.message)
            calculated_amount = amount_result.data

            if calculated_amount is None:
                return StepResult(success=False, message="Calculated amount is None")

            # 2c. 最小订单检查。
            min_result = runtime_checks.min_order_check(
                params, calculated_amount, entry_price
            )
            if not min_result.success:
                return StepResult(success=False, message=min_result.message)
            if min_result.data == "fail":
                return StepResult(success=True)

    # 3. 执行动作。
    exec_result = executor.execute_actions(
        params=params,
        actions=curr_signal.actions,
        entry_order_type=config.entry_order_type,
        calculated_amount=calculated_amount,
    )

    return StepResult(success=exec_result.success, message=exec_result.message)
