import asyncio
from datetime import datetime, timezone
from typing import Callable, Optional

from loguru import logger

from .bot_config import BotConfig
from .callbacks import Callbacks
from .runtime_checks import RuntimeChecks
from .executor import ActionExecutor
from .signal import SignalState
from .strategy_params import StrategyParams
from ._bot_process import default_signal_state, process_symbol
from ._bot_signal_execution import StepResult, execute_signal


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

        # 初始化执行组件。
        self.runtime_checks = RuntimeChecks(callbacks)
        self.executor = ActionExecutor(callbacks, self.runtime_checks)

        # 运行时状态。
        self._last_run_times: dict[str, datetime] = {}
        self._running = False

        # 统一日志输出格式。
        logger.remove()
        logger.add(
            lambda msg: print(msg, end=""),
            level=self.config.log_level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | {message}",
        )

    def _parse_period_minutes(self, base_data_key: str) -> int:
        """从 base_data_key 解析周期分钟数 (e.g. 'ohlcv_15m' -> 15)"""
        try:
            period_str = base_data_key.split("_")[-1]
            if period_str.endswith("m"):
                return int(period_str[:-1])
            if period_str.endswith("h"):
                return int(period_str[:-1]) * 60
            if period_str.endswith("d"):
                return int(period_str[:-1]) * 60 * 24
            return 15
        except (IndexError, ValueError):
            return 15

    def is_new_period(self, params: StrategyParams) -> bool:
        """判断是否到达新周期"""
        now = self.time_func()
        period_minutes = self._parse_period_minutes(params.base_data_key)

        if now.minute % period_minutes != 0:
            return False
        if now.second > 5:
            return False

        last_run = self._last_run_times.get(params.symbol)
        if not last_run:
            return True

        period_start = now.replace(second=0, microsecond=0)
        return last_run < period_start

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
        return await process_symbol(self.callbacks, self.config, params)

    def _execute_signal(
        self,
        params: StrategyParams,
        curr_signal: SignalState,
        prev_signal: SignalState,
        runtime_checks: RuntimeChecks,
        executor: ActionExecutor,
    ) -> StepResult:
        """执行信号动作"""
        return execute_signal(
            callbacks=self.callbacks,
            config=self.config,
            params=params,
            curr_signal=curr_signal,
            prev_signal=prev_signal,
            runtime_checks=runtime_checks,
            executor=executor,
        )

    def run_single_step(
        self,
        params: StrategyParams,
        signal: Optional[SignalState] = None,
        prev_signal: Optional[SignalState] = None,
    ) -> StepResult:
        """单步执行（测试用）"""
        curr = default_signal_state(signal)
        prev = default_signal_state(prev_signal)
        return self._execute_signal(
            params, curr, prev, self.runtime_checks, self.executor
        )

    def stop(self):
        """停止主循环"""
        self._running = False
        logger.info("交易机器人停止")
