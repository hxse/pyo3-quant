from typing import Optional, Literal
from loguru import logger

from .callback_result import CallbackResult
from .callbacks import Callbacks
from .models import (
    LimitOrderRequest,
    MarketOrderRequest,
    StopMarketOrderRequest,
    TakeProfitMarketOrderRequest,
    ClosePositionRequest,
    CancelAllOrdersRequest,
)
from .signal import SignalAction
from .strategy_params import StrategyParams
from .runtime_checks import RuntimeChecks


class ActionExecutor:
    """动作执行器，负责执行 SignalAction 列表"""

    def __init__(self, callbacks: Callbacks, runtime_checks: RuntimeChecks):
        self.callbacks = callbacks
        self.runtime_checks = runtime_checks

    def _map_side(
        self,
        signal_side: Literal["long", "short"],
        is_entry: bool,
    ) -> Literal["buy", "sell"]:
        """
        Side 映射：long/short -> buy/sell
        - 开多 (long 进场) -> buy
        - 开空 (short 进场) -> sell
        - 平多 (long 离场) -> sell
        - 平空 (short 离场) -> buy
        """
        if is_entry:
            return "buy" if signal_side == "long" else "sell"
        else:
            return "sell" if signal_side == "long" else "buy"

    def execute_actions(
        self,
        params: StrategyParams,
        actions: list[SignalAction],
        entry_order_type: Literal["limit", "market"],
        calculated_amount: Optional[float] = None,
    ) -> CallbackResult[bool]:
        """
        按顺序执行动作列表，任一失败则 Fail-Fast

        Args:
            params: 策略参数
            actions: 动作列表
            entry_order_type: 进场订单类型
            calculated_amount: 预先计算的下单数量（开仓时使用）
        """
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
        """执行单个动作"""

        if action.action_type == "close_position":
            return self._execute_close_position(params, action)

        elif action.action_type == "cancel_all_orders":
            return self._execute_cancel_all_orders(params, action)

        elif action.action_type in ("create_limit_order", "create_market_order"):
            # Enforce entry_order_type configuration
            if entry_order_type == "limit":
                if calculated_amount is None or calculated_amount <= 0:
                    logger.warning(
                        f"[{params.symbol}] 限价开仓跳过：无有效数量 (entry_order_type=limit)"
                    )
                    return CallbackResult(success=True, data=True)

                # If signal is market (no price), skip
                if action.price is None or action.price <= 0:
                    logger.error(
                        f"[{params.symbol}] Config is LIMIT but signal has no price. Skipping."
                    )
                    return CallbackResult(success=True, data=True)

                return self._execute_create_limit_order(
                    params, action, calculated_amount
                )

            elif entry_order_type == "market":
                if calculated_amount is None or calculated_amount <= 0:
                    logger.warning(
                        f"[{params.symbol}] 市价开仓跳过：无有效数量 (entry_order_type=market)"
                    )
                    return CallbackResult(success=True, data=True)

                return self._execute_create_market_order(
                    params, action, calculated_amount
                )

            else:
                return CallbackResult(
                    success=False,
                    message=f"Invalid entry_order_type: {entry_order_type}",
                )

        elif action.action_type == "create_stop_market_order":
            if calculated_amount is None or calculated_amount <= 0:
                logger.warning(f"[{params.symbol}] 止损单跳过：无有效数量")
                return CallbackResult(success=True, data=True)
            return self._execute_create_stop_order(params, action, calculated_amount)

        elif action.action_type == "create_take_profit_market_order":
            if calculated_amount is None or calculated_amount <= 0:
                logger.warning(f"[{params.symbol}] 止盈单跳过：无有效数量")
                return CallbackResult(success=True, data=True)
            return self._execute_create_tp_order(params, action, calculated_amount)

        else:
            logger.error(f"[{params.symbol}] 未知动作类型: {action.action_type}")
            return CallbackResult(
                success=False, message=f"Unknown action type: {action.action_type}"
            )

    def _execute_close_position(
        self, params: StrategyParams, action: SignalAction
    ) -> CallbackResult[bool]:
        logger.info(f"[{params.symbol}] 执行平仓")
        result = self.callbacks.close_position(
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
        self, params: StrategyParams, action: SignalAction
    ) -> CallbackResult[bool]:
        logger.info(f"[{params.symbol}] 取消所有挂单")
        result = self.callbacks.cancel_all_orders(
            CancelAllOrdersRequest(
                exchange_name=params.exchange_name,
                market=params.market,
                mode=params.mode,
                symbol=action.symbol,
            )
        )
        return CallbackResult(success=result.success, message=result.message)

    def _execute_create_limit_order(
        self, params: StrategyParams, action: SignalAction, amount: float
    ) -> CallbackResult[bool]:
        if action.side is None or action.price is None:
            return CallbackResult(
                success=False, message="Limit order requires side and price"
            )

        api_side = self._map_side(action.side, is_entry=True)
        logger.info(
            f"[{params.symbol}] 限价开仓: side={api_side}, price={action.price}, amount={amount}"
        )

        result = self.callbacks.create_limit_order(
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
        self, params: StrategyParams, action: SignalAction, amount: float
    ) -> CallbackResult[bool]:
        if action.side is None:
            return CallbackResult(success=False, message="Market order requires side")

        api_side = self._map_side(action.side, is_entry=True)
        logger.info(f"[{params.symbol}] 市价开仓: side={api_side}, amount={amount}")

        result = self.callbacks.create_market_order(
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
        self, params: StrategyParams, action: SignalAction, amount: float
    ) -> CallbackResult[bool]:
        if action.side is None or action.price is None:
            return CallbackResult(
                success=False, message="Stop order requires side and price"
            )

        # 止损单：平仓方向
        api_side = self._map_side(action.side, is_entry=False)
        logger.info(
            f"[{params.symbol}] 挂止损单: side={api_side}, triggerPrice={action.price}, amount={amount}"
        )

        result = self.callbacks.create_stop_market_order(
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
        self, params: StrategyParams, action: SignalAction, amount: float
    ) -> CallbackResult[bool]:
        if action.side is None or action.price is None:
            return CallbackResult(
                success=False, message="TP order requires side and price"
            )

        # 止盈单：平仓方向
        api_side = self._map_side(action.side, is_entry=False)
        logger.info(
            f"[{params.symbol}] 挂止盈单: side={api_side}, triggerPrice={action.price}, amount={amount}"
        )

        result = self.callbacks.create_take_profit_market_order(
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
