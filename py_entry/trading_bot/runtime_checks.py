from typing import Optional, Tuple, Literal
from loguru import logger
import math

from .callback_result import CallbackResult
from .callbacks import Callbacks
from .models import (
    PositionsResponse,
    BalanceResponse,
    MarketInfoResponse,
    CancelAllOrdersRequest,
)
from .signal import SignalState, SignalAction
from .strategy_params import StrategyParams


class RuntimeChecks:
    """运行时检查逻辑"""

    def __init__(self, callbacks: Callbacks):
        self.callbacks = callbacks

    def should_trigger_orphan_check(
        self,
        curr_signal: SignalState,
        prev_signal: SignalState,
    ) -> bool:
        """判断是否需要触发孤儿订单检查"""
        # 条件1: 当前信号即将开仓
        has_entry = any(
            a.action_type in ("create_limit_order", "create_market_order")
            for a in curr_signal.actions
        )
        # 条件2: 上一根有限价进场
        prev_has_limit = any(
            a.action_type == "create_limit_order" for a in prev_signal.actions
        )
        # 条件3: 上一根有任意离场
        prev_has_exit = prev_signal.has_exit

        return has_entry or prev_has_limit or prev_has_exit

    def orphan_order_check(
        self,
        params: StrategyParams,
    ) -> CallbackResult[bool]:
        """
        孤儿订单检查
        返回: success=True 表示检查通过（可能已清理或无需清理）
        """
        # 1. 查询持仓
        result = self.callbacks.fetch_positions(
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
            p.symbol == params.symbol and p.contracts and p.contracts > 0
            for p in positions
        )

        # 2. 无持仓则清理所有挂单
        if not has_position:
            logger.info(f"[{params.symbol}] 孤儿订单检查：无持仓，清理所有挂单")
            cancel_result = self.callbacks.cancel_all_orders(
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
        self,
        params: StrategyParams,
        signal_side: Literal["long", "short"],
    ) -> CallbackResult[Literal["proceed", "skip"]]:
        """
        重复开仓检查
        返回: "proceed" 允许开仓, "skip" 跳过开仓
        """
        result = self.callbacks.fetch_positions(
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
        for p in positions:
            if p.symbol == params.symbol and p.contracts and p.contracts > 0:
                if p.side == signal_side:
                    logger.info(
                        f"[{params.symbol}] 重复开仓检查：已有 {p.side} 持仓，跳过开仓"
                    )
                    return CallbackResult(success=True, data="skip")
                else:
                    logger.warning(
                        f"[{params.symbol}] 重复开仓检查：已有 {p.side} 持仓但信号为 {signal_side}，跳过"
                    )
                    return CallbackResult(success=True, data="skip")

        return CallbackResult(success=True, data="proceed")

    def calculate_order_amount(
        self,
        params: StrategyParams,
        entry_price: float,
    ) -> CallbackResult[float]:
        """
        计算下单数量
        公式: (余额 × 仓位% × 杠杆) / 价格，向下取整到交易所精度
        """
        # 1. 获取余额
        balance_result = self.callbacks.fetch_balance(
            exchange_name=params.exchange_name,
            market=params.market,
            mode=params.mode,
        )
        if not balance_result.success:
            return CallbackResult(
                success=False, message=f"fetch_balance failed: {balance_result.message}"
            )

        # 使用配置的结算币种
        currency = params.settlement_currency
        free_balance = (
            balance_result.data.balance.free.get(currency, 0.0)
            if balance_result.data
            else 0.0
        )

        # 2. 获取市场信息
        market_result = self.callbacks.fetch_market_info(
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
                success=False,
                message="fetch_market_info returned no data",
            )

        precision_amount = market_result.data.precision_amount

        # 3. 计算数量
        position_value = free_balance * params.position_size_pct * params.leverage
        raw_amount = position_value / entry_price

        # Strict Step Size Logic
        # We assume precision_amount is ALWAYS a Step Size (e.g. 0.001, 1.0, 5.0)
        try:
            step_size = float(precision_amount)
        except (ValueError, TypeError):
            logger.error(
                f"Invalid precision_amount: {precision_amount}, defaulting to 1.0"
            )
            step_size = 1.0

        if step_size <= 0:
            logger.warning(f"Invalid step_size {step_size} <= 0, defaulting to 1.0")
            step_size = 1.0

        # Formula: amount = floor(raw / step) * step
        # Using epsilon to avoid floating point issues (e.g. 10.0 / 0.1 = 99.999...)
        steps = math.floor(raw_amount / step_size + 1e-10)
        final_amount = steps * step_size

        logger.debug(
            f"[{params.symbol}] 下单计算: 余额={free_balance}, 仓位={params.position_size_pct}, "
            f"杠杆={params.leverage}, 价格={entry_price}, 数量={final_amount}, 步长={step_size}"
        )

        return CallbackResult(success=True, data=final_amount)

    def min_order_check(
        self,
        params: StrategyParams,
        amount: float,
        price: float,
    ) -> CallbackResult[Literal["pass", "fail"]]:
        """
        最小订单检查
        返回: "pass" 满足最小订单要求, "fail" 不满足
        """
        market_result = self.callbacks.fetch_market_info(
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
                success=False,
                message="fetch_market_info returned no data",
            )

        precision_amount = market_result.data.precision_amount
        min_amount = market_result.data.min_amount

        # Strict check: precision_amount must be valid > 0
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

        # Fallback: if min_amount is 0 or missing, use precision_amount (step size)
        if min_amount <= 0:
            min_amount = precision_val

        if amount < min_amount:
            logger.warning(
                f"[{params.symbol}] 最小订单检查失败：数量 {amount} < 最小数量 {min_amount}"
            )
            return CallbackResult(success=True, data="fail")

        return CallbackResult(success=True, data="pass")
