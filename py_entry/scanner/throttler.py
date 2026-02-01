"""扫描器节流控制工具"""

import time
import math
import logging
from .data_source import DataSourceProtocol

logger = logging.getLogger("scanner.throttler")


class TimeWindowThrottler:
    """时间窗口节流器

    仅在指定周期（例如5分钟）的整点前后的一段时间窗口内让程序处于活跃状态，
    其余时间让 TqSdk 保持低频心跳但不执行扫描逻辑。
    """

    def __init__(
        self,
        period_seconds: int = 300,
        window_seconds: int = 10,
        heartbeat_interval: int = 10,
    ):
        """
        Args:
            period_seconds: 基础周期，秒（如300表示5分钟）
            window_seconds: 窗口宽度，秒（整点前后各 window_seconds 秒）
            heartbeat_interval: 非窗口期维持心跳的调用间隔，秒
        """
        self.period = period_seconds
        self.window = window_seconds
        self.heartbeat = heartbeat_interval

    def wait_until_next_window(self, data_source: DataSourceProtocol) -> None:
        """
        阻塞直到进入下一个活跃窗口期。
        在等待期间，会定期调用 data_source.wait 进行心跳维护。
        """
        while True:
            now = time.time()
            if self._is_in_window(now):
                return

            # 计算距离下一个窗口还有多久
            # 下一个整点
            next_checkpoint = (math.ceil(now / self.period)) * self.period
            # 窗口开始时间 = 整点 - window
            window_start = next_checkpoint - self.window

            time_to_wait = window_start - now

            if time_to_wait <= 0:
                # 理论上应该已经被 _is_in_window 捕获，但防止边界情况
                return

            # 休眠策略：
            # 如果 wait 时间很长，分段 wait，每次 wait heartbeat 秒
            step_wait = min(time_to_wait, self.heartbeat)

            # 调用 data_source.wait 维持心跳 (但不期望有数据 update，或者有也不处理)
            # 注意：TqSdk wait_update 这里可能会因为数据推送而提前返回
            # 但既然我们在这个循环里，除了维持心跳我们不关心数据
            data_source.wait(step_wait)

    def _is_in_window(self, timestamp: float) -> bool:
        """判断当前时间是否在窗口期内"""
        # 归一化到周期内
        # 例如 period=300, now=301 -> mod=1. 在窗口内 (0-5 < 1 < 0+5)
        # now=299 -> mod=299. 也在窗口内 (300-5 < 299 < 300)

        mod = timestamp % self.period

        # 窗口范围： [0, window] U [period-window, period]
        if mod <= self.window:
            return True
        if mod >= (self.period - self.window):
            return True

        return False
