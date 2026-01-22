import asyncio
from datetime import datetime, timezone
from typing import Callable, Optional, Dict
from loguru import logger
import polars as pl

from .callbacks import Callbacks
from .bot_config import BotConfig
from .strategy_params import StrategyParams
from .signal import SignalState
from .runtime_checks import RuntimeChecks
from .executor import ActionExecutor
from .optimization import OptimizationCallbacks


class StepResult:
    """单步执行结果"""

    def __init__(self, success: bool, message: Optional[str] = None):
        self.success = success
        self.message = message


class TradingBot:
    """交易机器人主类"""

    def __init__(
        self,
        callbacks: Callbacks,
        config: Optional[BotConfig] = None,
        time_func: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
    ):
        self.callbacks = callbacks
        self.config = config or BotConfig()
        self.time_func = time_func

        # 组件
        self.runtime_checks = RuntimeChecks(callbacks)
        self.executor = ActionExecutor(callbacks, self.runtime_checks)

        # 状态
        self._last_run_times: Dict[str, datetime] = {}  # symbol -> last_run_time
        self._running = False

        # 配置日志
        logger.remove()
        logger.add(
            lambda msg: print(msg, end=""),
            level=self.config.log_level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        )

    def _parse_period_minutes(self, base_data_key: str) -> int:
        """从 base_data_key 解析周期分钟数 (e.g. 'ohlcv_15m' -> 15)"""
        try:
            # 使用 split('_') 获取最后一部分，即 timeframe (e.g. "15m")
            period_str = base_data_key.split("_")[-1]

            if period_str.endswith("m"):
                return int(period_str[:-1])
            elif period_str.endswith("h"):
                return int(period_str[:-1]) * 60
            elif period_str.endswith("d"):
                return int(period_str[:-1]) * 60 * 24
            else:
                return 15  # fallback
        except (IndexError, ValueError):
            return 15  # fallback

    def is_new_period(self, params: StrategyParams) -> bool:
        """判断是否到达新周期"""
        now = self.time_func()
        period_minutes = self._parse_period_minutes(params.base_data_key)

        # 检查是否在周期边界
        if now.minute % period_minutes != 0:
            return False
        if now.second > 5:  # 允许 5 秒的容差
            return False

        # 检查是否已在本周期执行过
        last_run = self._last_run_times.get(params.symbol)
        if last_run:
            # 计算周期起点
            period_start = now.replace(second=0, microsecond=0)
            if last_run >= period_start:
                return False  # 已执行过

        return True

    def _mark_period_executed(self, params: StrategyParams):
        """标记本周期已执行"""
        self._last_run_times[params.symbol] = self.time_func()

    async def run(self):
        """主循环"""
        self._running = True
        logger.info("交易机器人启动")

        while self._running:
            try:
                await self._run_cycle()
            except Exception as e:
                logger.error(f"主循环异常: {e}")

            await asyncio.sleep(self.config.loop_interval_sec)

    async def _run_cycle(self):
        """单次循环"""
        # 获取策略参数
        params_result = self.callbacks.get_strategy_params()
        if not params_result.success:
            logger.error(f"获取策略参数失败: {params_result.message}")
            return

        strategy_list = params_result.data or []

        for params in strategy_list:
            if not self.is_new_period(params):
                continue

            logger.info(f"[{params.symbol}] 到达新周期，开始执行")
            result = await self._process_symbol(params)

            if result.success:
                self._mark_period_executed(params)
            else:
                logger.error(f"[{params.symbol}] 执行失败: {result.message}")

    async def _process_symbol(self, params: StrategyParams) -> StepResult:
        """处理单个品种"""
        # 0. 创建 scoped optimization callbacks
        # 0. 创建 scoped optimization callbacks
        scoped_callbacks = OptimizationCallbacks(self.callbacks, params.symbol)

        # 注入代理到 RuntimeChecks 和 Executor
        scoped_runtime_checks = RuntimeChecks(scoped_callbacks)
        scoped_executor = ActionExecutor(scoped_callbacks, scoped_runtime_checks)

        # 1. 获取 OHLCV 数据
        ohlcv_result = self.callbacks.fetch_ohlcv(
            exchange_name=params.exchange_name,
            market=params.market,
            mode=params.mode,
            symbol=params.symbol,
            timeframe=params.base_data_key.split("_")[-1],
            since=None,
            limit=500,
            enable_cache=True,
            enable_test=False,
        )
        if not ohlcv_result.success:
            return StepResult(
                success=False, message=f"fetch_ohlcv failed: {ohlcv_result.message}"
            )

        # 转换为 DataFrame
        ohlcv_data = ohlcv_result.data or []
        df = pl.DataFrame(
            ohlcv_data,
            schema=["timestamp", "open", "high", "low", "close", "volume"],
            orient="row",
        )

        # 2. 运行回测
        backtest_result = self.callbacks.run_backtest(params, df)
        if not backtest_result.success:
            return StepResult(
                success=False, message=f"run_backtest failed: {backtest_result.message}"
            )

        bt_df = backtest_result.data
        if bt_df is None:
            return StepResult(success=False, message="Backtest data is None")

        # 3. 解析当前信号
        curr_result = self.callbacks.parse_signal(bt_df, params, index=-1)
        if not curr_result.success:
            return StepResult(
                success=False,
                message=f"parse_signal (curr) failed: {curr_result.message}",
            )
        curr_signal = curr_result.data
        if curr_signal is None:
            return StepResult(success=False, message="Current signal is None")

        # 4. 解析上一根信号
        prev_result = self.callbacks.parse_signal(bt_df, params, index=-2)
        if not prev_result.success:
            return StepResult(
                success=False,
                message=f"parse_signal (prev) failed: {prev_result.message}",
            )
        prev_signal = prev_result.data
        if prev_signal is None:
            return StepResult(success=False, message="Previous signal is None")

        # 5. 执行信号
        return self._execute_signal(
            params, curr_signal, prev_signal, scoped_runtime_checks, scoped_executor
        )

    def _execute_signal(
        self,
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

        # 判断是否有开仓动作
        entry_actions = [
            a
            for a in curr_signal.actions
            if a.action_type in ("create_limit_order", "create_market_order")
        ]
        has_entry = len(entry_actions) > 0

        # 1. 孤儿订单检查（条件触发）
        if runtime_checks.should_trigger_orphan_check(curr_signal, prev_signal):
            orphan_result = runtime_checks.orphan_order_check(params)
            if not orphan_result.success:
                return StepResult(success=False, message=orphan_result.message)

        calculated_amount: Optional[float] = None

        # 2. 开仓前检查
        if has_entry:
            entry_action = entry_actions[0]
            signal_side = entry_action.side
            entry_price = entry_action.price

            if signal_side is None:
                return StepResult(success=False, message="Entry action requires side")

            # 2a. 重复开仓检查
            dup_result = runtime_checks.duplicate_entry_check(params, signal_side)
            if not dup_result.success:
                return StepResult(success=False, message=dup_result.message)
            if dup_result.data == "skip":
                return StepResult(success=True)

            # 2b. 计算下单数量
            if entry_price is None:
                # 市价单需要获取当前价格
                ticker_result = self.callbacks.fetch_tickers(
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

                # 2c. 最小订单检查
                min_result = runtime_checks.min_order_check(
                    params, calculated_amount, entry_price
                )
                if not min_result.success:
                    return StepResult(success=False, message=min_result.message)
                if min_result.data == "fail":
                    return StepResult(success=True)  # 跳过但不算失败

        # 3. 执行动作
        exec_result = executor.execute_actions(
            params=params,
            actions=curr_signal.actions,
            entry_order_type=self.config.entry_order_type,
            calculated_amount=calculated_amount,
        )

        return StepResult(success=exec_result.success, message=exec_result.message)

    def run_single_step(
        self,
        params: StrategyParams,
        signal: Optional[SignalState] = None,
        prev_signal: Optional[SignalState] = None,
    ) -> StepResult:
        """
        单步执行（测试用）
        可直接传入预计算信号，跳过回测流程
        """
        if signal is None:
            signal = SignalState(actions=[])
        if prev_signal is None:
            prev_signal = SignalState(actions=[])

        return self._execute_signal(
            params, signal, prev_signal, self.runtime_checks, self.executor
        )

    def stop(self):
        """停止主循环"""
        self._running = False
        logger.info("交易机器人停止")
