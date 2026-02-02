"""扫描器防抖缓冲批处理器"""

import time
from .strategies.base import StrategySignal


class Batcher:
    """
    防抖缓冲批处理器

    负责收集信号，并根据静默时间进行防抖。
    只负责数据的收集和释放（flush），不包含任何 IO 或业务处理逻辑。
    """

    def __init__(self, buffer_seconds: float = 2.0):
        """
        Args:
            buffer_seconds: 防抖缓冲时间，秒。即静默多久后允许 Flush。
        """
        self.buffer_seconds = buffer_seconds

        self.signals: list[StrategySignal] = []
        self.last_arrival_time: float = 0.0
        self.is_collecting: bool = False

    def add(self, signal: StrategySignal):
        """添加单个信号，并刷新防抖计时器"""
        self.last_arrival_time = time.time()
        self.is_collecting = True
        self.signals.append(signal)

    def poke(self):
        """
        仅刷新防抖计时器 (Poke)

        用于明确表示"现在有活动"，即使没有产生信号，也希望推迟 flush 的时机。
        例如：K线刚更新完，虽然没信号，但可能意味着一波行情的结束，不希望立刻截断。
        """
        self.last_arrival_time = time.time()
        self.is_collecting = True

    def should_flush(self) -> bool:
        """
        判断是否应该释放数据 (Flush)

        条件：
        1. 必须处于收集状态 (is_collecting=True)
        2. 静默时间超过缓冲时间 (time.time() - last_arrival_time > buffer_seconds)
        """
        if not self.is_collecting:
            return False

        # Debounce: 必须要静默 buffer_seconds 秒后才放行
        if (time.time() - self.last_arrival_time) > self.buffer_seconds:
            return True

        return False

    def flush(self) -> list[StrategySignal]:
        """
        释放收集到的所有信号，并重置状态

        Returns:
            本批次收集的所有信号 (可能为空)
        """
        result = self.signals[:]

        # 重置状态，准备下一波
        self.signals.clear()
        self.is_collecting = False
        self.last_arrival_time = 0.0

        return result
