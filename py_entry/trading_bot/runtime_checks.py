from typing import Literal

from .callback_result import CallbackResult
from .callbacks import Callbacks
from .signal import SignalState
from .strategy_params import StrategyParams
from ._runtime_checks_logic import (
    calculate_order_amount,
    duplicate_entry_check,
    min_order_check,
    orphan_order_check,
    should_trigger_orphan_check,
)


class RuntimeChecks:
    """运行时检查逻辑。"""

    def __init__(self, callbacks: Callbacks):
        self.callbacks = callbacks

    def should_trigger_orphan_check(
        self,
        curr_signal: SignalState,
        prev_signal: SignalState,
    ) -> bool:
        """判断是否需要触发孤儿订单检查。"""
        return should_trigger_orphan_check(curr_signal, prev_signal)

    def orphan_order_check(self, params: StrategyParams) -> CallbackResult[bool]:
        """执行孤儿订单检查并按需清理挂单。"""
        return orphan_order_check(self.callbacks, params)

    def duplicate_entry_check(
        self,
        params: StrategyParams,
        signal_side: Literal["long", "short"],
    ) -> CallbackResult[Literal["proceed", "skip"]]:
        """执行重复开仓检查。"""
        return duplicate_entry_check(self.callbacks, params, signal_side)

    def calculate_order_amount(
        self,
        params: StrategyParams,
        entry_price: float,
    ) -> CallbackResult[float]:
        """根据账户与市场信息计算下单数量。"""
        return calculate_order_amount(self.callbacks, params, entry_price)

    def min_order_check(
        self,
        params: StrategyParams,
        amount: float,
        price: float,
    ) -> CallbackResult[Literal["pass", "fail"]]:
        """检查是否满足最小下单量。"""
        # 保留 price 参数用于兼容现有调用签名，当前逻辑不使用该值。
        _ = price
        return min_order_check(self.callbacks, params, amount)
