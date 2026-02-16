from typing import Literal, Optional

from loguru import logger

from .callback_result import CallbackResult
from .callbacks import Callbacks
from .runtime_checks import RuntimeChecks
from .signal import SignalAction
from .strategy_params import StrategyParams
from ._executor_actions import execute_single_action


class ActionExecutor:
    """动作执行器，负责执行 SignalAction 列表。"""

    def __init__(self, callbacks: Callbacks, runtime_checks: RuntimeChecks):
        self.callbacks = callbacks
        self.runtime_checks = runtime_checks

    def _map_side(
        self,
        signal_side: Literal["long", "short"],
        is_entry: bool,
    ) -> Literal["buy", "sell"]:
        """映射交易方向到交易所 side。"""
        if is_entry:
            return "buy" if signal_side == "long" else "sell"
        return "sell" if signal_side == "long" else "buy"

    def execute_actions(
        self,
        params: StrategyParams,
        actions: list[SignalAction],
        entry_order_type: Literal["limit", "market"],
        calculated_amount: Optional[float] = None,
    ) -> CallbackResult[bool]:
        """按顺序执行动作列表，任一失败则 Fail-Fast。"""
        for action in actions:
            result = self._execute_single_action(
                params=params,
                action=action,
                entry_order_type=entry_order_type,
                calculated_amount=calculated_amount,
            )
            if not result.success:
                logger.error(
                    f"[{params.symbol}] 执行动作失败: {action.action_type} - {result.message}"
                )
                return CallbackResult(
                    success=False,
                    message=f"Action {action.action_type} failed: {result.message}",
                )

        return CallbackResult(success=True, data=True)

    def _execute_single_action(
        self,
        params: StrategyParams,
        action: SignalAction,
        entry_order_type: Literal["limit", "market"],
        calculated_amount: Optional[float],
    ) -> CallbackResult[bool]:
        """执行单个动作。"""
        return execute_single_action(
            callbacks=self.callbacks,
            params=params,
            action=action,
            entry_order_type=entry_order_type,
            calculated_amount=calculated_amount,
            map_side=self._map_side,
        )
