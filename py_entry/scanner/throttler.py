"""扫描器节流器与周期追踪器"""

import time


class CycleTracker:
    """
    周期追踪器

    用于检测是否进入了新的时间周期（如每 5 分钟）。
    每个实例独立追踪自己的周期状态。
    """

    def __init__(self, period_seconds: int):
        """
        Args:
            period_seconds: 周期长度（秒），如 300 表示 5 分钟
        """
        self.period_seconds = period_seconds
        self._last_cycle_id: int = int(time.time() // period_seconds)

    def is_new_cycle(self) -> bool:
        """
        检测是否进入了新周期

        Returns:
            True 表示刚进入新周期（首次调用或周期变化时）
        """
        current_cycle_id = int(time.time() // self.period_seconds)
        if current_cycle_id > self._last_cycle_id:
            self._last_cycle_id = current_cycle_id
            return True
        return False

    def get_current_cycle_id(self) -> int:
        """获取当前周期 ID"""
        return int(time.time() // self.period_seconds)


class TimeWindowThrottler:
    """
    时间窗口节流器

    在每个周期的开头一段时间内保持活跃（窗口期），
    窗口期外则阻塞等待，节省资源。
    """

    def __init__(
        self,
        period_seconds: int,
        window_seconds: int,
        heartbeat_interval: float = 30.0,
    ):
        """
        Args:
            period_seconds: 周期长度（秒），如 300 表示 5 分钟
            window_seconds: 活跃窗口长度（秒），如 60 表示周期开始后 60 秒内活跃
            heartbeat_interval: 窗口外心跳间隔（秒），保持连接活跃
        """
        if window_seconds >= period_seconds // 2:
            raise ValueError(
                f"window_seconds ({window_seconds}) 必须小于 period_seconds 的一半 ({period_seconds // 2})"
            )

        self.period_seconds = period_seconds
        self.window_seconds = window_seconds
        self.heartbeat_interval = heartbeat_interval

        # 内置周期追踪器
        self.cycle_tracker = CycleTracker(period_seconds)

    def is_in_window(self) -> bool:
        """检查当前是否在活跃窗口内"""
        offset = time.time() % self.period_seconds
        return offset < self.window_seconds

    def wait_until_next_window(self, data_source) -> bool:
        """
        阻塞等待直到进入下一个活跃窗口

        在窗口外会持续睡眠，期间定期做心跳保持连接。

        Args:
            data_source: 数据源对象，用于调用 wait() 方法

        Returns:
            True 表示刚进入新周期（可用于触发 batcher.poke()）
        """
        if self.is_in_window():
            # 已经在窗口内，检查是否是新周期
            return self.cycle_tracker.is_new_cycle()

        # 窗口外，开始等待
        while not self.is_in_window():
            data_source.wait(self.heartbeat_interval)

        # 刚进入窗口，一定是新周期
        self.cycle_tracker._last_cycle_id = self.cycle_tracker.get_current_cycle_id()
        return True
