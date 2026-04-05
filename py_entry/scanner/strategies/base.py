from abc import ABC, abstractmethod

from py_entry.scanner.config import ScanLevel, TimeframeConfig

from ._scan_backtest import format_timestamp, run_scan_backtest
from ._scan_context import ScanContext
from ._signal_types import StrategyCheckResult, StrategySignal


class StrategyBase(ABC):
    """扫描策略基类。"""

    name: str

    def get_timeframes(self, defaults: list[TimeframeConfig]) -> list[TimeframeConfig]:
        """返回策略实际使用的周期画像；默认直接继承全局默认配置。"""
        return [tf.model_copy(deep=True) for tf in defaults]

    def get_watch_levels(self) -> list[ScanLevel]:
        """返回需要监听 bar 更新的逻辑级别；默认只监听 trigger。"""
        return [ScanLevel.TRIGGER]

    @abstractmethod
    def scan(self, ctx: ScanContext) -> StrategySignal | None:
        """执行扫描"""
        raise NotImplementedError
