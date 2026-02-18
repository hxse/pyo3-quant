"""
live 策略桥接回调。

作用：
1. 从 py_entry.private_strategies.live 读取已注册的 live 策略；
2. 输出交易机器人需要的 StrategyParams；
3. 使用 private live 自定义配置执行回测。
4. 不依赖 py_entry.strategies.get_strategy（private live 与公共策略解耦）。
"""

from typing import Any, Dict, List, Optional, Tuple
from collections import Counter

import polars as pl
from loguru import logger

from py_entry.data_generator import DirectDataConfig
from py_entry.runner import Backtest
from py_entry.private_strategies.live import get_live_strategy, get_live_strategy_names
from py_entry.private_strategies.live.base import LiveStrategyConfig

from .callback_result import CallbackResult
from .callbacks import Callbacks
from .signal import SignalState
from .strategy_params import StrategyParams


class LiveStrategyCallbacks:
    """
    将 live 注册表适配为 trading_bot 所需回调。

    说明：
    - 仅覆写 get_strategy_params 与 run_backtest；
    - 其余交易所/下单接口全部透传给 inner。
    """

    def __init__(
        self,
        inner: Callbacks,
        strategy_names: Optional[List[str]] = None,
    ):
        self._inner = inner
        all_entries = self._load_live_entries(strategy_names)
        # 仅启用策略进入机器人执行链路，关闭策略保留注册但不交易。
        self._entries = [entry for entry in all_entries if entry.enabled]
        if not self._entries:
            logger.warning("未发现任何 enabled live 策略，机器人本轮不会执行交易策略。")
        # 强约束：同一 symbol 只能有一个启用策略。
        symbol_counts = Counter(entry.symbol for entry in self._entries)
        duplicated_symbols = sorted(
            symbol for symbol, count in symbol_counts.items() if count > 1
        )
        if duplicated_symbols:
            raise ValueError(
                "live 策略配置冲突：同一 symbol 只能对应一个启用策略。"
                f"重复 symbol: {duplicated_symbols}"
            )
        self._params = [self._to_strategy_params(entry) for entry in self._entries]
        self._entry_by_key: Dict[Tuple[str, str], LiveStrategyConfig] = {
            (entry.symbol, entry.base_data_key): entry for entry in self._entries
        }

    def _load_live_entries(
        self,
        strategy_names: Optional[List[str]],
    ) -> List[LiveStrategyConfig]:
        """加载并校验 live 策略条目。"""
        names = strategy_names or get_live_strategy_names()
        if not names:
            raise ValueError(
                "未发现任何 live 策略，请先在 py_entry.private_strategies.live 注册"
            )
        return [get_live_strategy(name) for name in names]

    def _to_strategy_params(self, entry: LiveStrategyConfig) -> StrategyParams:
        """将 live 策略配置转换为 bot 运行参数。"""
        return StrategyParams(
            base_data_key=entry.base_data_key,
            symbol=entry.symbol,
            exchange_name=entry.exchange_name,
            market=entry.market,
            mode=entry.mode,
            position_size_pct=entry.position_size_pct,
            leverage=entry.leverage,
            settlement_currency=entry.settlement_currency,
        )

    def get_strategy_params(self) -> CallbackResult[List[StrategyParams]]:
        """返回 live 策略列表给机器人主循环。"""
        return CallbackResult(success=True, data=self._params)

    def run_backtest(
        self,
        params: StrategyParams,
        df: pl.DataFrame,
    ) -> CallbackResult[pl.DataFrame]:
        """
        使用 live 注册策略执行回测并返回回测 DataFrame。

        这里强制使用 DirectDataConfig，把机器人当前拉取的数据喂给回测。
        """
        try:
            entry = self._entry_by_key.get((params.symbol, params.base_data_key))
            if entry is None:
                return CallbackResult(
                    success=False,
                    message=(
                        f"未找到 symbol={params.symbol}, "
                        f"base_data_key={params.base_data_key} 对应的 live 策略"
                    ),
                )

            # 机器人 fetch_ohlcv 产物是 timestamp 列，回测数据层使用 time 列。
            source_df = (
                df.rename({"timestamp": "time"})
                if "timestamp" in df.columns and "time" not in df.columns
                else df
            )

            data_source = DirectDataConfig(
                data={params.base_data_key: source_df},
                base_data_key=params.base_data_key,
            )

            bt = Backtest(
                data_source=data_source,
                indicators=entry.strategy.indicators_params,
                signal=entry.strategy.signal_params,
                backtest=entry.strategy.backtest_params,
                signal_template=entry.strategy.signal_template,
                engine_settings=entry.strategy.engine_settings,
                performance=entry.strategy.performance_params,
            )
            run_result = bt.run()
            backtest_df = run_result.summary.backtest_result
            if backtest_df is None:
                return CallbackResult(success=False, message="回测结果为空")
            return CallbackResult(success=True, data=backtest_df)
        except Exception as exc:
            return CallbackResult(
                success=False,
                message=f"live run_backtest 失败: {exc}",
            )

    def parse_signal(
        self,
        df: pl.DataFrame,
        params: StrategyParams,
        index: int = -1,
    ) -> CallbackResult[SignalState]:
        """信号解析沿用 inner 实现。"""
        return self._inner.parse_signal(df, params, index)

    def __getattr__(self, name: str) -> Any:
        """其余 callback 透传给 inner。"""
        return getattr(self._inner, name)
